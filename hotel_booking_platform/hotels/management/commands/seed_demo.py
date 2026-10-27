from decimal import Decimal

from django.core.management.base import BaseCommand

from hotels.models import Hotel, Room

DEMO = [
    ("Seaside Grand", "Goa", "12 Beach Road", "Beachfront hotel with a pool and sea views.",
     [("101", "single", 1, 60), ("102", "double", 2, 95), ("201", "suite", 4, 220)]),
    ("City Lights Inn", "Bengaluru", "45 MG Road", "Modern rooms in the heart of the city.",
     [("1", "single", 1, 45), ("2", "double", 2, 70), ("3", "family", 5, 130)]),
    ("Hilltop Retreat", "Ooty", "7 Tea Estate Lane", "Quiet cottage-style stay among tea gardens.",
     [("A1", "double", 2, 85), ("A2", "family", 4, 140)]),
]


class Command(BaseCommand):
    help = "Create demo hotels and rooms"

    def handle(self, *args, **options):
        for name, city, address, desc, rooms in DEMO:
            hotel, _ = Hotel.objects.get_or_create(
                name=name, defaults={"city": city, "address": address, "description": desc}
            )
            for number, rtype, cap, price in rooms:
                Room.objects.get_or_create(
                    hotel=hotel, number=number,
                    defaults={"room_type": rtype, "capacity": cap, "price_per_night": Decimal(price)},
                )
        self.stdout.write(self.style.SUCCESS("Demo data created."))
