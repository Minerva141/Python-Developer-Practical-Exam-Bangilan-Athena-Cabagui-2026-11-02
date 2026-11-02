"""python manage.py seed_cars [count]  -> fills the table with random cars."""
import random
from django.core.management.base import BaseCommand
from cars.models import Car, GAP

COLORS = ["blue", "red", "green", "yellow", "black", "white"]


class Command(BaseCommand):
    help = "Create N sample cars (default 100000)."

    def add_arguments(self, parser):
        parser.add_argument("count", nargs="?", type=int, default=100_000)

    def handle(self, *args, **opts):
        Car.objects.all().delete()
        cars = [Car(name=f"Car {i}", color=random.choice(COLORS), position=i * GAP)
                for i in range(1, opts["count"] + 1)]
        Car.objects.bulk_create(cars, batch_size=5000)
        self.stdout.write(self.style.SUCCESS(f"Created {opts['count']} cars"))
