import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Booking, Review
from .payments import luhn_ok


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%d")
        super().__init__(**kwargs)


class SearchForm(forms.Form):
    city = forms.CharField(required=False)
    check_in = forms.DateField(required=False, widget=DateInput())
    check_out = forms.DateField(required=False, widget=DateInput())
    guests = forms.IntegerField(required=False, min_value=1, max_value=10, initial=1)

    def clean(self):
        cd = super().clean()
        ci, co = cd.get("check_in"), cd.get("check_out")
        if bool(ci) != bool(co):
            raise forms.ValidationError("Please choose both check-in and check-out dates.")
        if ci and co:
            if co <= ci:
                raise forms.ValidationError("Check-out must be after check-in.")
            if ci < timezone.localdate():
                raise forms.ValidationError("Check-in cannot be in the past.")
        return cd


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ["check_in", "check_out", "guests"]
        widgets = {"check_in": DateInput(), "check_out": DateInput()}

    def __init__(self, *args, room, **kwargs):
        super().__init__(*args, **kwargs)
        self.room = room
        self.instance.room = room  # model.clean() needs the room for validation


class PaymentForm(forms.Form):
    card_name = forms.CharField(max_length=80, label="Name on card")
    card_number = forms.CharField(max_length=23, label="Card number")
    expiry = forms.CharField(max_length=5, label="Expiry (MM/YY)")
    cvc = forms.CharField(max_length=4, label="CVC")

    def clean_card_number(self):
        number = self.cleaned_data["card_number"].replace(" ", "").replace("-", "")
        if not luhn_ok(number):
            raise forms.ValidationError("Enter a valid card number.")
        return number

    def clean_expiry(self):
        value = self.cleaned_data["expiry"].strip()
        m = re.fullmatch(r"(\d{2})/(\d{2})", value)
        if not m or not 1 <= int(m.group(1)) <= 12:
            raise forms.ValidationError("Use the format MM/YY.")
        month, year = int(m.group(1)), 2000 + int(m.group(2))
        today = timezone.localdate()
        if (year, month) < (today.year, today.month):
            raise forms.ValidationError("This card has expired.")
        return value

    def clean_cvc(self):
        value = self.cleaned_data["cvc"].strip()
        if not re.fullmatch(r"\d{3,4}", value):
            raise forms.ValidationError("Enter a 3 or 4 digit CVC.")
        return value


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(
        choices=[(i, f"{i} star{'s' if i > 1 else ''}") for i in range(5, 0, -1)], coerce=int
    )

    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 4})}


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]
