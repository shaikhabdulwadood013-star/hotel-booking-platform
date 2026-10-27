from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import payments
from .forms import BookingForm, PaymentForm, RegisterForm, ReviewForm, SearchForm
from .models import Booking, Hotel, Payment, Review, Room


def register(request):
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        messages.success(request, "Welcome! Your account has been created.")
        return redirect("hotel_list")
    return render(request, "registration/register.html", {"form": form})


def hotel_list(request):
    form = SearchForm(request.GET or None)
    hotels = Hotel.objects.all()
    qs = ""
    if form.is_valid():
        cd = form.cleaned_data
        if cd["city"]:
            hotels = hotels.filter(city__icontains=cd["city"])
        if cd["check_in"] and cd["check_out"]:
            booked = Booking.blocking().filter(
                check_in__lt=cd["check_out"], check_out__gt=cd["check_in"]
            ).values("room_id")
            free = Room.objects.filter(
                is_active=True, capacity__gte=cd["guests"] or 1
            ).exclude(pk__in=booked)
            hotels = hotels.filter(rooms__in=free).distinct()
            qs = urlencode({
                "check_in": cd["check_in"], "check_out": cd["check_out"], "guests": cd["guests"] or 1,
            })
    return render(request, "hotels/list.html", {"form": form, "hotels": hotels, "qs": qs})


def hotel_detail(request, pk):
    hotel = get_object_or_404(Hotel, pk=pk)
    form = SearchForm(request.GET or None)
    check_in = check_out = None
    guests, nights, qs = 1, 0, ""
    if form.is_valid() and form.cleaned_data["check_in"]:
        check_in, check_out = form.cleaned_data["check_in"], form.cleaned_data["check_out"]
        guests = form.cleaned_data["guests"] or 1
        nights = (check_out - check_in).days
        qs = urlencode({"check_in": check_in, "check_out": check_out, "guests": guests})

    rooms = list(hotel.rooms.filter(is_active=True))
    for room in rooms:
        if check_in:
            room.available = room.capacity >= guests and room.is_available(check_in, check_out)
            room.total = room.price_per_night * nights
        else:
            room.available = None

    can_review = False
    if request.user.is_authenticated:
        stayed = Booking.objects.filter(
            user=request.user, room__hotel=hotel, status=Booking.CONFIRMED,
            check_out__lte=timezone.localdate(),
        ).exists()
        can_review = stayed and not Review.objects.filter(user=request.user, hotel=hotel).exists()

    return render(request, "hotels/detail.html", {
        "hotel": hotel, "form": form, "rooms": rooms, "qs": qs, "nights": nights,
        "reviews": hotel.reviews.select_related("user"), "can_review": can_review,
    })


@login_required
def book_room(request, room_id):
    room = get_object_or_404(Room.objects.select_related("hotel"), pk=room_id, is_active=True)
    initial = {k: request.GET[k] for k in ("check_in", "check_out", "guests") if k in request.GET}
    form = BookingForm(request.POST or None, room=room, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            Room.objects.select_for_update().get(pk=room.pk)  # serialise concurrent bookings
            if room.is_available(form.cleaned_data["check_in"], form.cleaned_data["check_out"]):
                booking = form.save(commit=False)
                booking.user = request.user
                booking.save()
                messages.info(request, "Room reserved. Complete payment to confirm your booking.")
                return redirect("pay_booking", pk=booking.pk)
            form.add_error(None, "Sorry, someone just booked this room for those dates.")
    return render(request, "hotels/book.html", {"form": form, "room": room})


@login_required
def pay_booking(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("room__hotel"), pk=pk, user=request.user)
    if not booking.can_pay:
        messages.info(request, "This booking does not need payment.")
        return redirect("my_bookings")

    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        with transaction.atomic():
            Room.objects.select_for_update().get(pk=booking.room_id)
            if not booking.room.is_available(booking.check_in, booking.check_out, exclude=booking):
                booking.status = Booking.CANCELLED
                booking.save(update_fields=["status"])
                messages.error(request, "Your hold expired and the room was taken. Please search again.")
                return redirect("hotel_detail", pk=booking.room.hotel_id)

            result = payments.charge(booking.total_price, cd["card_number"], cd["expiry"], cd["cvc"])
            Payment.objects.create(
                booking=booking, amount=booking.total_price,
                status=Payment.SUCCEEDED if result.success else Payment.FAILED,
                transaction_id=result.transaction_id, card_last4=cd["card_number"][-4:],
            )
            if result.success:
                booking.status = Booking.CONFIRMED
                booking.save(update_fields=["status"])
                messages.success(request, "Payment successful - your booking is confirmed!")
                return redirect("my_bookings")
            form.add_error(None, result.message)
    return render(request, "hotels/payment.html", {"form": form, "booking": booking})


@login_required
def my_bookings(request):
    bookings = request.user.bookings.select_related("room__hotel").prefetch_related("payments")
    return render(request, "hotels/my_bookings.html", {"bookings": bookings})


@login_required
@require_POST
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if not booking.can_cancel:
        messages.error(request, "This booking can no longer be cancelled.")
    else:
        with transaction.atomic():
            paid = booking.payments.filter(status=Payment.SUCCEEDED).first()
            if paid and payments.refund(paid.transaction_id):
                paid.status = Payment.REFUNDED
                paid.save(update_fields=["status"])
            booking.status = Booking.CANCELLED
            booking.save(update_fields=["status"])
        messages.success(request, "Booking cancelled." + (" Your payment was refunded." if paid else ""))
    return redirect("my_bookings")


@login_required
def add_review(request, pk):
    hotel = get_object_or_404(Hotel, pk=pk)
    stayed = Booking.objects.filter(
        user=request.user, room__hotel=hotel, status=Booking.CONFIRMED,
        check_out__lte=timezone.localdate(),
    ).exists()
    if not stayed:
        messages.error(request, "You can review a hotel after completing a stay there.")
        return redirect("hotel_detail", pk=pk)
    if Review.objects.filter(user=request.user, hotel=hotel).exists():
        messages.info(request, "You have already reviewed this hotel.")
        return redirect("hotel_detail", pk=pk)

    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.user, review.hotel = request.user, hotel
        review.save()
        messages.success(request, "Thanks for your review!")
        return redirect("hotel_detail", pk=pk)
    return render(request, "hotels/review_form.html", {"form": form, "hotel": hotel})
