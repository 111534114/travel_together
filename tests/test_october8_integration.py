import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from flask import render_template, session
from werkzeug.datastructures import MultiDict

from app import app
from blueprints.member import (
    ITEM_TYPE_LABELS, _load_votes, _open_vote_progress, _parse_expense_items,
    _parse_itinerary_time, _summarize_transport_time,
)
import theme_parks


class October8IntegrationTests(unittest.TestCase):
    def test_time_modes_and_transport_summary(self):
        data = dict(start_time='09:00', end_time='18:00', transport_minutes='35')
        self.assertEqual(_parse_itinerary_time(dict(data, time_mode='all_day')),
                         (None, None, True, 35, []))
        self.assertEqual(_parse_itinerary_time(dict(data, time_mode='start_only'))[:3],
                         ('09:00', None, False))
        self.assertTrue(_parse_itinerary_time(dict(data, transport_minutes='-1'))[-1])
        self.assertEqual(_summarize_transport_time([
            dict(transport_method='火車', transport_minutes=35),
            dict(transport_method='火車', transport_minutes=25),
        ]), [dict(method='火車', minutes=60)])

    def test_votes_preserve_reasons_and_voter_ids(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [dict(vote_id=7, vote_type='approval')], [], [dict(user_id=2)],
            [dict(approval_choice='disagree', c=1)], [dict(reason='時間不合')],
        ]
        cursor.fetchone.return_value = dict(option_id=None, approval_choice='disagree', reason='時間不合')
        result = _load_votes(cursor, 1, 2)[0]
        self.assertEqual(result['voter_ids'], [2])
        self.assertEqual(result['my_reason'], '時間不合')
        self.assertEqual(result['disagree_reasons'], [dict(reason='時間不合')])

    def test_vote_progress_includes_accepted_viewers(self):
        cursor = MagicMock()
        cursor.fetchall.side_effect = [
            [dict(vote_id=7, title='晚餐', deadline_at=datetime(2026, 12, 1, 12))],
            [dict(user_id=1)],
        ]
        members = [dict(user_id=1, full_name='Owner', nickname='', member_role='owner'),
                   dict(user_id=2, full_name='Viewer', nickname='', member_role='viewer')]
        result = _open_vote_progress(cursor, 1, members)[0]
        self.assertEqual(result['pending'], [dict(user_id=2, name='Viewer')])

    def test_invoice_items_keep_row_keys_and_totals(self):
        form = MultiDict([('item_key', '3'), ('item_key', '9'),
                          ('item_desc_3', '午餐'), ('item_amount_3', '120.50')])
        items = _parse_expense_items(form, {}, '2026-10-10')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['amount'], Decimal('120.50'))
        self.assertEqual(items[0]['date'], date(2026, 10, 10))

    def test_park_outage_uses_matching_date_from_cache(self):
        park = theme_parks.DISNEY_PARKS[0]
        schedule = [dict(date='2026-10-10', type='OPERATING',
                         openingTime='2026-10-10T09:00:00+09:00',
                         closingTime='2026-10-10T21:00:00+09:00')]
        with patch.dict(theme_parks._schedule_cache, {park['entity_id']: (0, schedule)}, clear=True), \
             patch('theme_parks.requests.get', side_effect=theme_parks.requests.ConnectionError('offline')):
            result = theme_parks.get_park_hours(park['id'], '2026-10-10')
            self.assertEqual(result['opening_time'], '09:00')
            self.assertIsNone(theme_parks.get_park_hours(park['id'], '2026-10-11'))

    def test_trip_page_combines_all_features_for_editor_and_viewer(self):
        today = date(2026, 10, 10)
        trip = dict(trip_id=1, trip_name='整合測試', country='台灣', city='台北',
                    start_date=today, end_date=today, member_role='owner',
                    currency='TWD', total_budget=1000, people_count=2, status='planning',
                    visibility='private', cover_image_path=None, introduction='')
        item = dict(itinerary_id=1, itinerary_date=today, title='測試景點',
                    item_type='attraction', is_all_day=False, start_time=timedelta(hours=9),
                    end_time=timedelta(hours=10), estimated_cost=0, transport_minutes=30,
                    transport_method='火車', address='', notes='', detail_attraction_id=3,
                    attraction_hours='09:00–17:00', attraction_description='景點詳細介紹')
        vote = dict(vote_id=7, title='晚餐', vote_type='approval', status='open',
                    deadline_at=datetime(2026, 12, 1), created_by=1, total_votes=1,
                    creator_name='Owner', agree_count=0, disagree_count=1, neutral_count=0,
                    voter_ids=[1], options=[], my_approval_choice='disagree', my_reason='時間不合',
                    disagree_reasons=[dict(full_name='Owner', nickname='', reason='時間不合')])
        member = dict(user_id=1, full_name='Owner', nickname='', member_role='owner')
        viewer = dict(user_id=2, full_name='Viewer', nickname='', member_role='viewer')
        attraction = dict(attraction_id=3, name='測試景點', city='台北', city_id=1, ticket_price=0)
        expense = dict(expense_name='午餐', expense_date=today, payer_name='Owner',
                       scope='personal', amount=120, note='', splits=[],
                       items=[dict(item_date=today, description='餐點', amount=120, receipt_path=None)])
        for can_edit in (True, False):
            with self.subTest(can_edit=can_edit), app.test_request_context('/member/trips/1'):
                session.update(user_id=1 if can_edit else 2, role='member')
                html = render_template('member/trip_detail.html', trip=trip, itinerary=[item],
                    city_weather_days={}, place_options={}, popular_attractions=[attraction],
                    addable_trips=[trip], members=[member, viewer], pending_invitations=[],
                    proposals=[], votes=[vote], comments=[], expenses=[expense],
                    balance_summary=[], attachments=[], actual=120, can_edit=can_edit,
                    is_owner=can_edit, now=datetime(2026, 10, 10),
                    item_type_labels=ITEM_TYPE_LABELS, disney_parks=theme_parks.get_disney_parks(),
                    transport_summary=[dict(method='火車', minutes=30)])
                for section in ('itinerary', 'proposals', 'chat', 'budget'):
                    self.assertEqual(html.count('id="'+section+'"'), 1)
                for text in ('09:00', '景點詳細介紹', '時間不合', '發票明細', 'split_user_ids', 'Viewer', 'trip-chat.js', 'expense-invoice.js'):
                    self.assertIn(text, html)
                if can_edit:
                    self.assertIn('data-attraction-preview="attraction-preview-3"', html)
                    self.assertIn('time-mode-select', html)
                    self.assertIn('park-hours-trigger', html)
                self.assertIn('/member/trips/1/votes/7/cast', html)


if __name__ == '__main__':
    unittest.main()
