from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Booking, Hotel, Payment, Room


class BookingFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sam", password="pass12345")
        self.hotel = Hotel.objects.create(name="H", city="C", address="A")
        self.room = Room.objects.create(
            hotel=self.hotel, number="1", capacity=2, price_per_night=Decimal("100")
        )
        self.today = timezone.localdate()

    def make(self, start, end, status=Booking.CONFIRMED):
        return Booking.objects.create(
            user=self.user, room=self.room, status=status,
            check_in=self.today + timedelta(days=start), check_out=self.today + timedelta(days=end),
        )

    def test_total_price_calculated(self):
        self.assertEqual(self.make(1, 4).total_price, Decimal("300"))

    def test_overlap_blocks_but_back_to_back_allowed(self):
        self.make(2, 5)
        d = lambda n: self.today + timedelta(days=n)
        self.assertFalse(self.room.is_available(d(4), d(6)))
        self.assertTrue(self.room.is_available(d(5), d(7)))
        self.assertTrue(self.room.is_available(d(0), d(2)))

    def test_expired_pending_hold_releases_room(self):
        b = self.make(2, 5, status=Booking.PENDING)
        Booking.objects.filter(pk=b.pk).update(created_at=timezone.now() - timedelta(hours=2))
        self.assertTrue(self.room.is_available(b.check_in, b.check_out))

    def test_payment_confirms_booking(self):
        self.client.login(username="sam", password="pass12345")
        b = self.make(2, 4, status=Booking.PENDING)
        data = {"card_name": "Sam", "card_number": "4242 4242 4242 4242", "expiry": "12/40", "cvc": "123"}
        self.client.post(reverse("pay_booking", args=[b.pk]), data)
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.CONFIRMED)
        self.assertEqual(b.payments.get().status, Payment.SUCCEEDED)

    def test_declined_card_keeps_booking_pending(self):
        self.client.login(username="sam", password="pass12345")
        b = self.make(2, 4, status=Booking.PENDING)
        data = {"card_name": "Sam", "card_number": "4000 0000 0000 0002", "expiry": "12/40", "cvc": "123"}
        self.client.post(reverse("pay_booking", args=[b.pk]), data)
        b.refresh_from_db()
        self.assertEqual(b.status, Booking.PENDING)
        self.assertEqual(b.payments.get().status, Payment.FAILED)
