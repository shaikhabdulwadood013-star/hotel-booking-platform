from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Min, Q
from django.utils import timezone


class Hotel(models.Model):
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    address = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.city})"

    @property
    def average_rating(self):
        return self.reviews.aggregate(avg=Avg("rating"))["avg"]

    @property
    def starting_price(self):
        return self.rooms.filter(is_active=True).aggregate(m=Min("price_per_night"))["m"]


class Room(models.Model):
    SINGLE, DOUBLE, SUITE, FAMILY = "single", "double", "suite", "family"
    TYPE_CHOICES = [
        (SINGLE, "Single"),
        (DOUBLE, "Double"),
        (SUITE, "Suite"),
        (FAMILY, "Family"),
    ]

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="rooms")
    number = models.CharField(max_length=10)
    room_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=DOUBLE)
    capacity = models.PositiveSmallIntegerField(default=2)
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("hotel", "number")
        ordering = ["hotel", "number"]

    def __str__(self):
        return f"{self.hotel.name} - Room {self.number}"

    def is_available(self, check_in, check_out, exclude=None):
        """True if no blocking booking overlaps [check_in, check_out).
        Back-to-back stays (check-out day == next check-in day) are allowed."""
        if not self.is_active:
            return False
        overlapping = Booking.blocking().filter(
            room=self, check_in__lt=check_out, check_out__gt=check_in
        )
        if exclude is not None and exclude.pk:
            overlapping = overlapping.exclude(pk=exclude.pk)
        return not overlapping.exists()


class Booking(models.Model):
    PENDING, CONFIRMED, CANCELLED = "pending", "confirmed", "cancelled"
    STATUS_CHOICES = [
        (PENDING, "Pending payment"),
        (CONFIRMED, "Confirmed"),
        (CANCELLED, "Cancelled"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name="bookings")
    check_in = models.DateField()
    check_out = models.DateField()
    guests = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Booking #{self.pk} - {self.room} ({self.check_in} to {self.check_out})"

    @classmethod
    def blocking(cls):
        """Bookings that currently hold a room: confirmed, or unexpired pending holds."""
        cutoff = timezone.now() - timedelta(minutes=settings.BOOKING_HOLD_MINUTES)
        return cls.objects.filter(
            Q(status=cls.CONFIRMED) | Q(status=cls.PENDING, created_at__gte=cutoff)
        )

    @property
    def nights(self):
        return (self.check_out - self.check_in).days

    @property
    def can_pay(self):
        return self.status == self.PENDING

    @property
    def can_cancel(self):
        return self.status in (self.PENDING, self.CONFIRMED) and self.check_in > timezone.localdate()

    @property
    def can_review(self):
        return self.status == self.CONFIRMED and self.check_out <= timezone.localdate()

    def clean(self):
        if not (self.check_in and self.check_out and self.room_id):
            return
        if self.check_out <= self.check_in:
            raise ValidationError("Check-out must be after check-in.")
        if not self.pk and self.check_in < timezone.localdate():
            raise ValidationError("Check-in cannot be in the past.")
        if self.guests > self.room.capacity:
            raise ValidationError(f"This room sleeps at most {self.room.capacity} guests.")
        if self.status in (self.PENDING, self.CONFIRMED) and not self.room.is_available(
            self.check_in, self.check_out, exclude=self
        ):
            raise ValidationError("Sorry, this room is not available for those dates.")

    def save(self, *args, **kwargs):
        if not self.total_price and self.check_in and self.check_out:
            self.total_price = self.room.price_per_night * self.nights
        super().save(*args, **kwargs)


class Payment(models.Model):
    PENDING, SUCCEEDED, FAILED, REFUNDED = "pending", "succeeded", "failed", "refunded"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SUCCEEDED, "Succeeded"),
        (FAILED, "Failed"),
        (REFUNDED, "Refunded"),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    transaction_id = models.CharField(max_length=64, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)  # never store full card numbers
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.transaction_id or self.pk} ({self.status})"


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews")
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "hotel")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.hotel} ({self.rating}/5)"
