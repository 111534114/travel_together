from datetime import date
from decimal import Decimal, InvalidOperation
import secrets

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from auth import login_required
from db import get_db_connection
from utils import format_hm

booking_bp = Blueprint('booking', __name__)
TABLES = {'hotel': ('accommodations', 'accommodation_id'), 'flight': ('flights', 'flight_id'), 'train': ('trains', 'train_id')}
ENDPOINTS = {'visitor_hotel_search': 'hotel', 'visitor_flight_search': 'flight', 'visitor_train_search': 'train'}
FARES = {'all': '全部票種', 'regular': '一般票', 'discount': '打折票', 'promotion': '優惠票', 'student': '學生票'}
TRAIN_TYPE_LABELS = {'thsr': '高鐵', 'tra': '台鐵'}
TIME_BANDS = [
    ('dawn', '凌晨 00:00–06:00', '00:00', '06:00'),
    ('morning', '上午 06:00–12:00', '06:00', '12:00'),
    ('afternoon', '下午 12:00–18:00', '12:00', '18:00'),
    ('evening', '晚上 18:00–24:00', '18:00', '24:00'),
]

TRAIN_TYPE_LABELS = {'thsr': '高鐵', 'tra': '台鐵'}

# 出發時段的固定區間(模仿常見訂票網站的「凌晨/上午/下午/晚上」分段)
TIME_BANDS = [
    ('dawn', '凌晨 00:00–06:00', '00:00', '06:00'),
    ('morning', '上午 06:00–12:00', '06:00', '12:00'),
    ('afternoon', '下午 12:00–18:00', '12:00', '18:00'),
    ('evening', '晚上 18:00–24:00', '18:00', '24:00'),
]


def validate_search(kind, args):
    fields = {'hotel': [('destination', '目的地'), ('checkin', '入住日期'), ('checkout', '退房日期')],
              'flight': [('from', '出發地'), ('to', '目的地'), ('depart', '去程日期')],
              'train': [('from', '出發站'), ('to', '到達站'), ('date', '去程日期')]}[kind]
    mode = args.get('trip_mode', 'roundtrip' if kind == 'flight' else 'oneway')
    if kind != 'hotel' and mode == 'roundtrip':
        fields = fields + [('return', '回程日期')]
    errors = {key: '請填寫' + label for key, label in fields if not args.get(key, '').strip()}
    if kind != 'hotel' and mode not in ('oneway', 'roundtrip'):
        errors['trip_mode'] = '請選擇單程或來回'
    dates = {}
    for key in ('checkin', 'checkout') if kind == 'hotel' else (('depart', 'return') if kind == 'flight' else ('date', 'return')):
        if kind != 'hotel' and key == 'return' and mode == 'oneway':
            continue
        value = args.get(key, '')
        if value:
            try:
                dates[key] = date.fromisoformat(value)
                if dates[key] < date.today():
                    errors[key] = '日期不能早於今天'
            except ValueError:
                errors[key] = '請填寫有效日期'
    start, end = ('checkin', 'checkout') if kind == 'hotel' else ('depart' if kind == 'flight' else 'date', 'return')
    if start in dates and end in dates and (dates[end] < dates[start] or (kind == 'hotel' and dates[end] == dates[start])):
        errors[end] = '退房日期必須晚於入住' if kind == 'hotel' else '回程不能早於去程'
    if kind != 'hotel' and args.get('from', '').strip() and args.get('from', '').strip() == args.get('to', '').strip():
        errors['to'] = '出發地與目的地不能相同'
    for key in ('min_price', 'max_price'):
        if args.get(key):
            try:
                value = Decimal(args[key])
                if not value.is_finite() or value < 0 or value > 100000000:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                errors[key] = '請輸入有效的非負金額'
    if not any(k in errors for k in ('min_price', 'max_price')) and args.get('min_price') and args.get('max_price'):
        if Decimal(args['min_price']) > Decimal(args['max_price']):
            errors['max_price'] = '最高預算不能小於最低預算'
    if args.get('fare', 'all') not in FARES:
        errors['fare'] = '請選擇有效票種'
    if kind == 'flight' and args.get('stops', '') not in ('', 'direct', 'connecting'):
        errors['stops'] = '請選擇有效的轉機條件'
    count_key = 'guests' if kind == 'hotel' else 'pax'
    if args.get(count_key) and (not args[count_key].isdigit() or not 1 <= int(args[count_key]) <= 99):
        errors[count_key] = '人數須介於 1 與 99'
    return errors


@booking_bp.before_app_request
def guard_search():
    kind = ENDPOINTS.get(request.endpoint)
    if not kind or not request.args:
        return None
    errors = validate_search(kind, request.args)
    if not errors:
        return None
    return render_template(kind + '_search.html', search_errors=errors,
                           destination=request.args.get('destination' if kind == 'hotel' else 'to', ''),
                           origin=request.args.get('from', ''), checkin=request.args.get('checkin', ''),
                           checkout=request.args.get('checkout', ''), depart_date=request.args.get('depart', ''),
                           return_date=request.args.get('return', ''), travel_date=request.args.get('date', ''),
                           guests=2, pax=1, nights=None, accommodations=[], outbound_flights=[], return_flights=[], trains=[],
                           price_buckets=[], airline_facets=[], train_type_facets=[], car_class_facets=[], depart_band_options=[]), 400
def price_buckets(rows, field, count=4):
    """依照目前搜尋結果的實際價格分布，動態切出幾個價格區間(仿照常見訂票網站的做法，
    不是寫死固定的級距)。結果數量或價格種類太少時切不出有意義的區間，就不提供篩選。"""
    all_prices = sorted(float(r[field]) for r in rows if r.get(field) and r[field] > 0)
    unique_prices = sorted(set(all_prices))
    if len(unique_prices) < count:
        return []

    step = 50 if unique_prices[-1] < 2000 else (100 if unique_prices[-1] < 10000 else 500)
    def nice(value):
        return int(round(value / step) * step)

    n = len(unique_prices)
    edges = sorted({0} | {nice(unique_prices[min(int(i * n / count), n - 1)]) for i in range(1, count)})

    buckets = []
    for i, low in enumerate(edges):
        high = edges[i + 1] if i + 1 < len(edges) else None
        matched = sum(1 for p in all_prices if p >= low and (high is None or p < high))
        if matched:
            buckets.append({'low': low, 'high': high, 'count': matched})
    return buckets


def facet_options(rows, field, labels=None):
    """算出目前搜尋結果裡，某個欄位(例如航空公司、車種)有哪些不同的值可以勾選篩選，
    附帶各自的筆數與顯示用文字；只有 2 種以上的值才有篩選意義，否則回傳空清單(不顯示篩選)。"""
    counts = {}
    for row in rows:
        value = row.get(field)
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    if len(counts) < 2:
        return []
    return sorted(
        ({'value': value, 'label': (labels or {}).get(value, value), 'count': count} for value, count in counts.items()),
        key=lambda opt: -opt['count']
    )


def apply_facets(rows, fields):
    """fields 是 [(資料欄位, 網址參數名稱), ...] 的清單；每個參數用 checkbox 多選，
    使用者有勾選才會篩選，沒勾就不限制。"""
    result = rows
    for field, param in fields:
        selected = request.args.getlist(param)
        if selected:
            result = [row for row in result if row.get(field) in selected]
    return result


def time_band_options(rows, field):
    options = []
    for key, label, start, end in TIME_BANDS:
        count = sum(1 for row in rows if row.get(field) and start <= format_hm(row[field]) < end)
        if count:
            options.append({'value': key, 'label': label, 'count': count})
    return options if len(options) >= 2 else []

def apply_time_band(rows, field):
    selected = request.args.getlist('depart_band')
    if not selected:
        return rows
    bands = [b for b in TIME_BANDS if b[0] in selected]
    def matches(row):
        value = row.get(field)
        if not value:
            return False
        hm = format_hm(value)
        return any(start <= hm < end for _, _, start, end in bands)
    return [row for row in rows if matches(row)]


def filter_prices(rows, field, duration_field=None, stops_field=None):
    low = Decimal(request.args.get('min_price') or '0')
    high = Decimal(request.args['max_price']) if request.args.get('max_price') else None
    fare = request.args.get('fare', 'all')
    stops_filter = request.args.get('stops', '') if stops_field else ''
    result = []
    for row in rows:
        # Existing transport records are standard fares; no discount is inferred.
        if fare not in ('all', row.get('fare_type', 'regular')):
            continue
        if stops_filter == 'direct' and row.get(stops_field):
            continue
        if stops_filter == 'connecting' and not row.get(stops_field):
            continue
        price = row.get(field)
        known = price is not None and price > 0
        if (low or high is not None) and (not known or price < low or (high is not None and price > high)):
            continue
        result.append(row)
    sort = request.args.get('sort', '')
    if sort in ('price_asc', 'price_desc'):
        result.sort(key=lambda r: (not bool(r.get(field)), (r.get(field) or 0) * (-1 if sort == 'price_desc' else 1)))
    elif sort == 'featured' and duration_field:
        # 精選：同時考慮價格與耗時，概算每分鐘車程/航程約值 NT$20，取總分最低的排前面。
        result.sort(key=lambda r: (not bool(r.get(field)), (r.get(field) or 0) + (r.get(duration_field) or 0) * 20))
    return result


@booking_bp.app_context_processor
def booking_context():
    session.setdefault('booking_csrf', secrets.token_urlsafe(32))
    saved = set()
    if session.get('role') == 'member' and (request.endpoint in ENDPOINTS or request.endpoint == 'booking.favorites'):
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            try:
                cursor.execute('SELECT kind,target_id FROM booking_favorites WHERE user_id=%s', (session['user_id'],))
                saved = set(cursor.fetchall())
            finally:
                cursor.close(); connection.close()
    return dict(booking_saved=saved, booking_csrf=session['booking_csrf'], fare_options=FARES,
                booking_kind=ENDPOINTS.get(request.endpoint))


@booking_bp.route('/member/booking-favorites/<kind>/<int:target_id>', methods=['POST'])
@login_required('member')
def save_favorite(kind, target_id):
    if kind not in TABLES:
        abort(404)
    if not secrets.compare_digest(request.form.get('csrf', ''), session.get('booking_csrf', '!')):
        abort(400)
    action = request.form.get('action')
    if action not in ('save', 'remove'):
        abort(400)
    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor()
    try:
        if action == 'save':
            table, key = TABLES[kind]
            extra = ' AND deleted_at IS NULL' if kind == 'hotel' else ''
            cursor.execute(f"SELECT {key} FROM {table} WHERE {key}=%s AND status='active'" + extra, (target_id,))
            if not cursor.fetchone():
                abort(404)
            cursor.execute('INSERT IGNORE INTO booking_favorites(user_id,kind,target_id) VALUES (%s,%s,%s)', (session['user_id'], kind, target_id))
        else:
            cursor.execute('DELETE FROM booking_favorites WHERE user_id=%s AND kind=%s AND target_id=%s', (session['user_id'], kind, target_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close(); connection.close()
    target = request.form.get('next', '')
    if not target.startswith(('/visitor/hotels', '/visitor/flights', '/visitor/trains', '/member/booking-favorites')) or '\\' in target or '\r' in target or '\n' in target:
        target = url_for('booking.favorites')
    return redirect(target)


@booking_bp.route('/member/booking-favorites')
@login_required('member')
def favorites():
    connection = get_db_connection()
    if connection is None:
        abort(503)
    cursor = connection.cursor(dictionary=True)
    groups = {}
    try:
        for kind, (table, key) in TABLES.items():
            cursor.execute(f'SELECT f.target_id, t.* FROM booking_favorites f LEFT JOIN {table} t ON t.{key}=f.target_id WHERE f.user_id=%s AND f.kind=%s ORDER BY f.created_at DESC', (session['user_id'], kind))
            groups[kind] = cursor.fetchall()
    finally:
        cursor.close(); connection.close()
    return render_template('member/booking_favorites.html', groups=groups)
