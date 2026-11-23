"""小機場(只飛國內線，例如花蓮、澎湖)的組合行程：把「小機場→轉運站」的國內航班，
接上「轉運站→目的地」的國際航班，組成一張完整行程卡。兩段是分開購買的機票，
所以要預留足夠的轉機時間(行李需自行提領、重新報到)。"""
from datetime import datetime

from serpapi_flights import _fmt_minutes

STAMP = "%Y-%m-%d %H:%M"
MIN_CONNECTION_MINUTES = 150  # 分開購買的兩張票，至少要留 2.5 小時才算可行的轉機
MAX_CONNECTION_MINUTES = 24 * 60


def _dt(value):
    try:
        return datetime.strptime(value, STAMP)
    except (TypeError, ValueError):
        return None


PRICE_WINDOW_MINUTES = 90  # 比「最短等待」多 90 分鐘以內的班次才互相比價格


def _pick(candidates):
    """candidates: [(價格, 等待分鐘, 其他資料...)]。回傳等待最短(容許 90 分鐘內)裡價格最低的那一筆。"""
    shortest = min(c[1] for c in candidates)
    near = [c for c in candidates if c[1] <= shortest + PRICE_WINDOW_MINUTES]
    return min(near, key=lambda c: (c[0], c[1]))


def combine_with_domestic(domestic, international, feeder_code, feeder_name=""):
    """domestic：小機場→轉運站的國內航班清單；international：轉運站出發的國際航班清單。
    每一班國際航班配「抵達時間夠早、價格最低」的那一班國內航班；配不到的國際航班就不列出。"""
    legs = []
    for flight in domestic:
        segments = flight.get("segments") or []
        if not segments or flight.get("stops"):
            continue
        dep, arr = _dt(segments[0].get("dep_dt")), _dt(segments[-1].get("arr_dt"))
        if dep and arr:
            legs.append((flight, dep, arr))

    combined = []
    for flight in international:
        segments = flight.get("segments") or []
        if flight.get("origin_city") != feeder_code or not segments:
            continue
        intl_dep = _dt(segments[0].get("dep_dt"))
        if not intl_dep:
            continue
        options = []
        for leg, dep, arr in legs:
            gap = (intl_dep - arr).total_seconds() / 60
            if MIN_CONNECTION_MINUTES <= gap <= MAX_CONNECTION_MINUTES:
                options.append((leg["price"], gap, leg, dep, arr))
        if not options:
            continue
        _, gap, leg, dep, arr = _pick(options)

        first_leg = [dict(seg) for seg in leg["segments"]]
        first_leg[-1]["layover"] = {
            "duration": _fmt_minutes(gap), "name": feeder_name or feeder_code, "iata": feeder_code,
            "overnight": arr.date() != intl_dep.date(), "separate": True,
        }
        item = dict(flight)
        item["segments"] = first_leg + [dict(seg) for seg in segments]
        item["price"] = flight["price"] + leg["price"]
        item["stops"] = (flight.get("stops") or 0) + 1
        item["origin_city"] = leg.get("origin_city")
        item["departure_time"] = leg.get("departure_time")
        intl_arr = _dt(segments[-1].get("arr_dt"))
        item["duration_minutes"] = int((intl_arr - dep).total_seconds() / 60) if intl_arr else (
            (leg.get("duration_minutes") or 0) + int(gap) + (flight.get("duration_minutes") or 0))
        item["layovers"] = [{"iata": feeder_code, "name": feeder_name or feeder_code, "duration_minutes": int(gap)}] + list(flight.get("layovers") or [])
        item["layover_minutes"] = max((l["duration_minutes"] for l in item["layovers"] if l.get("duration_minutes")), default=None)
        item["combined_domestic"] = True
        item["domestic_price"] = leg["price"]
        item["flight_id"] = f"{flight.get('flight_id')}+{leg.get('flight_id')}"
        combined.append(item)
    return combined


def combine_with_domestic_tail(international, domestic, feeder_code, feeder_name=""):
    """目的地是小機場：國際航班先抵達轉運站，再接「轉運站→目的地小機場」的國內航班。
    每一班國際航班配「起飛時間夠晚(至少 2.5 小時後)、價格最低」的那一班國內航班；配不到的就不列出。"""
    legs = []
    for flight in domestic:
        segments = flight.get("segments") or []
        if not segments or flight.get("stops"):
            continue
        dep, arr = _dt(segments[0].get("dep_dt")), _dt(segments[-1].get("arr_dt"))
        if dep and arr:
            legs.append((flight, dep, arr))

    combined = []
    for flight in international:
        segments = flight.get("segments") or []
        if flight.get("destination_city") != feeder_code or not segments:
            continue
        intl_arr = _dt(segments[-1].get("arr_dt"))
        intl_dep = _dt(segments[0].get("dep_dt"))
        if not intl_arr or not intl_dep:
            continue
        options = []
        for leg, dep, arr in legs:
            gap = (dep - intl_arr).total_seconds() / 60
            if MIN_CONNECTION_MINUTES <= gap <= MAX_CONNECTION_MINUTES:
                options.append((leg["price"], gap, leg, dep, arr))
        if not options:
            continue
        _, gap, leg, dep, arr = _pick(options)

        intl_segments = [dict(seg) for seg in segments]
        intl_segments[-1]["layover"] = {
            "duration": _fmt_minutes(gap), "name": feeder_name or feeder_code, "iata": feeder_code,
            "overnight": intl_arr.date() != dep.date(), "separate": True,
        }
        item = dict(flight)
        item["segments"] = intl_segments + [dict(seg) for seg in leg["segments"]]
        item["price"] = flight["price"] + leg["price"]
        item["stops"] = (flight.get("stops") or 0) + 1
        item["destination_city"] = leg.get("destination_city")
        item["arrival_time"] = leg.get("arrival_time")
        item["duration_minutes"] = int((arr - intl_dep).total_seconds() / 60)
        item["layovers"] = list(flight.get("layovers") or []) + [{"iata": feeder_code, "name": feeder_name or feeder_code, "duration_minutes": int(gap)}]
        item["layover_minutes"] = max((l["duration_minutes"] for l in item["layovers"] if l.get("duration_minutes")), default=None)
        item["combined_domestic"] = True
        item["domestic_price"] = leg["price"]
        item["flight_id"] = f"{flight.get('flight_id')}+{leg.get('flight_id')}"
        combined.append(item)
    return combined
