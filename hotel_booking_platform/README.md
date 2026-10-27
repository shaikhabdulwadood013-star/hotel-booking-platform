# StayEase – Hotel Booking Platform (Django)

Features: hotel & room listings, date-based availability search, reservations (with
payment hold + cancellation), mock payment processing with refunds, and verified-guest reviews.

## Run it
```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations hotels
python manage.py migrate
python manage.py seed_demo          # sample hotels and rooms
python manage.py createsuperuser    # for /admin/
python manage.py runserver
```
Open http://127.0.0.1:8000/ and the admin at /admin/.

Run tests: `python manage.py test`

## How it works
- **Availability**: a room is free if no confirmed booking (or unexpired pending hold) overlaps the dates.
  Back-to-back stays are allowed. Holds last `BOOKING_HOLD_MINUTES` (settings.py).
- **Payments**: `hotels/payments.py` is a mock gateway. Test cards: `4242 4242 4242 4242` succeeds,
  `4000 0000 0000 0002` is declined. Only the last 4 digits are stored. Swap in Stripe/Razorpay for production.
- **Reviews**: only users with a confirmed, completed stay can review (one review per hotel).

## Before deploying
Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`; switch to PostgreSQL;
use a real payment provider.
