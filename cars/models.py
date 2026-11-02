"""
Data model for the ordered car list.

ORDERING STRATEGY: "gapped positions"
-------------------------------------
Every car stores an integer ``position``. The list order is simply
``ORDER BY position, id``. Positions are spaced ``GAP`` apart, so a car can be
moved between two neighbours by giving it the midpoint of their positions:
that is ONE UPDATE of ONE ROW, regardless of list size (100,000 cars or 10M).

If two neighbours ever become adjacent (no integer left between them) we
"rebalance": renumber everything with fresh gaps. With GAP = 2**20 a single
spot can be halved 20 times before that happens, so rebalancing is very rare
(and is O(n) only then).

Filtering by colour keeps the global order because the composite index
(color, position) is already sorted by position within each colour.
"""
from django.db import models, transaction
from django.db.models import Case, IntegerField, Max, When

GAP = 2 ** 20


class CarQuerySet(models.QuerySet):
    def in_order(self):
        return self.order_by("position", "id")

    def of_color(self, color):
        return self.filter(color__iexact=color) if color else self

    def search(self, text):
        """
        Case-insensitive 'contains' search on the car name, with a relevance
        rank: 0 = exact name, 1 = name starts with the text, 2 = contains it.
        Searching "car 85" therefore lists "Car 85" before "Car 850", "Car 8500"...
        """
        if not text:
            return self
        return self.filter(name__icontains=text).annotate(
            match_rank=Case(
                When(name__iexact=text, then=0),
                When(name__istartswith=text, then=1),
                default=2,
                output_field=IntegerField(),
            )
        )


class Car(models.Model):
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=30)
    position = models.BigIntegerField()

    objects = CarQuerySet.as_manager()

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            # "show blue cars" in order -> single index range scan, no sort.
            models.Index(fields=["color", "position"], name="car_color_pos_idx"),
            # Unfiltered ordered list / neighbour lookups.
            models.Index(fields=["position"], name="car_pos_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.color})"

    def save(self, *args, **kwargs):
        self.color = self.color.strip().lower()
        if self.position is None:
            self.position = Car.next_tail_position()
        super().save(*args, **kwargs)

    # ---------- ordering helpers ----------
    @staticmethod
    def next_tail_position():
        top = Car.objects.aggregate(m=Max("position"))["m"]
        return GAP if top is None else top + GAP

    @staticmethod
    def rebalance():
        """Renumber all cars with fresh gaps (rare, O(n))."""
        with transaction.atomic():
            cars = list(Car.objects.in_order().only("id", "position"))
            for i, car in enumerate(cars, start=1):
                car.position = i * GAP
            Car.objects.bulk_update(cars, ["position"], batch_size=5000)

    def move_before(self, target):
        """Place this car directly in front of ``target``. Updates 1 row."""
        self._move(target, before=True)

    def move_after(self, target):
        """Place this car directly after ``target``. Updates 1 row."""
        self._move(target, before=False)

    def _move(self, target, before):
        if target.pk == self.pk:
            return
        for attempt in range(2):  # second attempt only after a rebalance
            target.refresh_from_db(fields=["position"])
            others = Car.objects.exclude(pk=self.pk)
            if before:
                neighbour = (others.filter(position__lt=target.position)
                             .order_by("-position", "-id").first())
                lo = neighbour.position if neighbour else target.position - 2 * GAP
                hi = target.position
            else:
                neighbour = (others.filter(position__gt=target.position)
                             .order_by("position", "id").first())
                lo = target.position
                hi = neighbour.position if neighbour else target.position + 2 * GAP
            new_pos = (lo + hi) // 2
            if lo < new_pos < hi:
                Car.objects.filter(pk=self.pk).update(position=new_pos)
                self.position = new_pos
                return
            Car.rebalance()  # no room left between neighbours
        raise RuntimeError("could not find a free position after rebalance")