from django.contrib import admin

from .models import Booking, Hotel, Payment, Review, Room


class RoomInline(admin.TabularInline):
    model = Room
    extra = 1


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "created_at")
    search_fields = ("name", "city")
    inlines = [RoomInline]


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("hotel", "number", "room_type", "capacity", "price_per_night", "is_active")
    list_filter = ("hotel", "room_type", "is_active")


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ("amount", "status", "transaction_id", "card_last4", "created_at")
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "room", "check_in", "check_out", "status", "total_price")
    list_filter = ("status", "room__hotel")
    search_fields = ("user__username", "room__hotel__name")
    date_hierarchy = "check_in"
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("transaction_id", "booking", "amount", "status", "created_at")
    list_filter = ("status",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("hotel", "user", "rating", "created_at")
    list_filter = ("rating", "hotel")
