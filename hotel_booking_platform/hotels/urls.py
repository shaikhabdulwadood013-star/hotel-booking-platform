from django.urls import path

from . import views

urlpatterns = [
    path("", views.hotel_list, name="hotel_list"),
    path("hotels/<int:pk>/", views.hotel_detail, name="hotel_detail"),
    path("hotels/<int:pk>/review/", views.add_review, name="add_review"),
    path("rooms/<int:room_id>/book/", views.book_room, name="book_room"),
    path("bookings/", views.my_bookings, name="my_bookings"),
    path("bookings/<int:pk>/pay/", views.pay_booking, name="pay_booking"),
    path("bookings/<int:pk>/cancel/", views.cancel_booking, name="cancel_booking"),
    path("register/", views.register, name="register"),
]
