import unittest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app import app
from booking_search import filter_prices, validate_search


class BookingSearchTests(unittest.TestCase):
    def setUp(self):
        self.day = (date.today() + timedelta(days=10)).isoformat()
        self.later = (date.today() + timedelta(days=12)).isoformat()
        self.client = app.test_client()

    def test_required_and_roundtrip_dates(self):
        self.assertIn('destination', validate_search('hotel', {}))
        args = {'from': 'A', 'to': 'B', 'depart': self.day}
        self.assertIn('return', validate_search('flight', args))
        args['trip_mode'] = 'oneway'
        self.assertEqual(validate_search('flight', args), {})
        args = {'from': 'A', 'to': 'B', 'date': self.day, 'trip_mode': 'roundtrip'}
        self.assertIn('return', validate_search('train', args))

    def test_invalid_dates_destinations_and_budget(self):
        args = {'destination': 'Jiufen', 'checkin': self.day, 'checkout': self.day, 'max_price': 'NaN'}
        errors = validate_search('hotel', args)
        self.assertIn('checkout', errors)
        self.assertIn('max_price', errors)
        errors = validate_search('train', {'from': 'A', 'to': 'A', 'date': 'bad'})
        self.assertIn('to', errors)
        self.assertIn('date', errors)

    def test_price_filter_excludes_unknown_prices(self):
        rows = [{'price': None}, {'price': Decimal('800')}, {'price': Decimal('400')}, {'price': 0}]
        with app.test_request_context('/?max_price=500&sort=price_asc'):
            self.assertEqual(filter_prices(rows, 'price'), [{'price': Decimal('400')}])
        with app.test_request_context('/?fare=student'):
            self.assertEqual(filter_prices(rows, 'price'), [])

    def test_invalid_search_blocked_before_query(self):
        with patch('app.get_db_connection') as connection:
            response = self.client.get('/visitor/hotels?destination=Jiufen')
        self.assertEqual(response.status_code, 400)
        connection.assert_not_called()
        self.assertIn(b'booking-errors', response.data)

    def login(self, user_id):
        with self.client.session_transaction() as session:
            session['user_id'] = user_id
            session['role'] = 'member'
            session['booking_csrf'] = 'test-token'

    def test_save_and_remove_are_scoped_to_current_member(self):
        self.login(42)
        for action in ('save', 'remove'):
            connection = MagicMock()
            connection.cursor.return_value.fetchone.return_value = (7,)
            with patch('booking_search.get_db_connection', return_value=connection):
                response = self.client.post('/member/booking-favorites/hotel/7', data={'csrf':'test-token', 'action':action, 'next':'https://example.com'})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, '/member/booking-favorites')
            self.assertEqual(connection.cursor.return_value.execute.call_args.args[1], (42,'hotel',7))
            connection.commit.assert_called_once()

    def test_favorites_require_login_and_csrf(self):
        self.assertEqual(self.client.post('/member/booking-favorites/train/1').status_code, 302)
        self.login(42)
        with patch('booking_search.get_db_connection') as connection:
            response = self.client.post('/member/booking-favorites/train/1', data={'action':'save'})
        self.assertEqual(response.status_code, 400)
        connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
