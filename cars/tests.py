from django.test import TestCase
from django.urls import reverse

from .models import Car, GAP


def names(qs):
    return [c.name for c in qs.in_order()]


class ExampleFromProblemTests(TestCase):
    """The exact example from the exam: D B E C A with D,E,A blue."""

    def setUp(self):
        self.c = {}
        for name, color in [("D", "blue"), ("B", "red"), ("E", "blue"),
                            ("C", "red"), ("A", "blue")]:
            self.c[name] = Car.objects.create(name=name, color=color)

    def test_initial_order(self):
        self.assertEqual(names(Car.objects.all()), list("DBECA"))

    def test_blue_cars_in_order(self):
        self.assertEqual(names(Car.objects.of_color("blue")), ["D", "E", "A"])

    def test_move_c_before_b_and_d_before_a(self):
        self.c["C"].move_before(self.c["B"])
        self.c["D"].move_before(self.c["A"])
        self.assertEqual(names(Car.objects.all()), list("CBEDA"))
        self.assertEqual(names(Car.objects.of_color("blue")), ["E", "D", "A"])

    def test_move_updates_only_one_row(self):
        before = dict(Car.objects.values_list("id", "position"))
        self.c["C"].move_before(self.c["B"])
        after = dict(Car.objects.values_list("id", "position"))
        changed = [i for i in before if before[i] != after[i]]
        self.assertEqual(changed, [self.c["C"].id])

    def test_move_to_front_and_end(self):
        self.c["A"].move_before(self.c["D"])
        self.assertEqual(names(Car.objects.all()), list("ADBEC"))
        self.c["A"].move_after(self.c["C"])
        self.assertEqual(names(Car.objects.all()), list("DBECA"))

    def test_move_after_middle(self):
        self.c["D"].move_after(self.c["E"])
        self.assertEqual(names(Car.objects.all()), list("BEDCA"))


class RebalanceTests(TestCase):
    def test_gap_exhaustion_triggers_rebalance_and_keeps_order(self):
        a = Car.objects.create(name="A", color="red")
        b = Car.objects.create(name="B", color="red")
        movers = [Car.objects.create(name=f"M{i}", color="red") for i in range(40)]
        # Keep inserting directly in front of B: halves the gap every time.
        for m in movers:
            m.move_before(b)
        order = names(Car.objects.all())
        self.assertEqual(order, ["A"] + [m.name for m in movers] + ["B"])
        self.assertTrue(all(c.position % 1 == 0 for c in Car.objects.all()))

    def test_rebalance_spreads_positions(self):
        for i in range(5):
            Car.objects.create(name=str(i), color="red", position=i)
        Car.rebalance()
        self.assertEqual([c.position for c in Car.objects.in_order()],
                         [GAP * i for i in range(1, 6)])


class ViewTests(TestCase):
    def setUp(self):
        self.a = Car.objects.create(name="A", color="Blue ")
        self.b = Car.objects.create(name="B", color="red")

    def test_color_normalised(self):
        self.assertEqual(self.a.color, "blue")

    def test_list_filter(self):
        r = self.client.get(reverse("car_list"), {"color": "blue"})
        self.assertContains(r, "A")
        self.assertEqual([c.name for c in r.context["page"]], ["A"])

    def test_create_edit_delete(self):
        self.client.post(reverse("car_create"), {"name": "Z", "color": "green"})
        z = Car.objects.get(name="Z")
        self.assertEqual(Car.objects.in_order().last(), z)  # appended
        self.client.post(reverse("car_edit", args=[z.id]), {"name": "Z2", "color": "green"})
        z.refresh_from_db()
        self.assertEqual(z.name, "Z2")
        self.client.post(reverse("car_delete", args=[z.id]))
        self.assertFalse(Car.objects.filter(pk=z.pk).exists())

    def test_move_endpoint(self):
        r = self.client.post(reverse("car_move", args=[self.b.id]), {"before": self.a.id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(names(Car.objects.all()), ["B", "A"])

    def test_move_endpoint_requires_target(self):
        r = self.client.post(reverse("car_move", args=[self.b.id]), {})
        self.assertEqual(r.status_code, 400)


class SearchTests(TestCase):
    def setUp(self):
        Car.objects.create(name="Beetle", color="blue")
        Car.objects.create(name="Mustang", color="red")
        Car.objects.create(name="Blue Beetle Mk2", color="red")

    def test_search_is_case_insensitive_and_ordered(self):
        r = self.client.get(reverse("car_list"), {"q": "BEETLE"})
        self.assertEqual([c.name for c in r.context["page"]], ["Beetle", "Blue Beetle Mk2"])

    def test_search_combined_with_color(self):
        r = self.client.get(reverse("car_list"), {"q": "beetle", "color": "red"})
        self.assertEqual([c.name for c in r.context["page"]], ["Blue Beetle Mk2"])

    def test_pagination_links_keep_filters(self):
        for i in range(60):
            Car.objects.create(name=f"Beetle {i}", color="blue")
        r = self.client.get(reverse("car_list"), {"q": "beetle", "color": "blue"})
        self.assertContains(r, "color=blue&amp;q=beetle&amp;page=2")

    def test_create_redirects_to_last_page(self):
        r = self.client.post(reverse("car_create"), {"name": "New", "color": "green"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("page=", r["Location"])


class SearchRankingTests(TestCase):
    def test_exact_match_comes_before_longer_names(self):
        Car.objects.create(name="Car 850", color="red")
        Car.objects.create(name="Car 8500", color="red")
        Car.objects.create(name="Old Car 85", color="red")
        exact = Car.objects.create(name="Car 85", color="blue")  # last in list order
        r = self.client.get(reverse("car_list"), {"q": "car 85"})
        found = [c.name for c in r.context["page"]]
        self.assertEqual(found[0], "Car 85")
        self.assertEqual(found, ["Car 85", "Car 850", "Car 8500", "Old Car 85"])


class EditModalTests(TestCase):
    def setUp(self):
        self.car = Car.objects.create(name="Old", color="red")

    def test_list_page_has_edit_modal_with_car_data(self):
        r = self.client.get(reverse("car_list"))
        self.assertContains(r, 'id="editModal"')
        self.assertContains(r, 'data-name="Old"')
        self.assertContains(r, f'data-action="/cars/{self.car.id}/edit/"')

    def test_edit_returns_to_next_page(self):
        r = self.client.post(reverse("car_edit", args=[self.car.id]),
                             {"name": "New", "color": "Blue", "next": "/?color=red&page=2"})
        self.assertRedirects(r, "/?color=red&page=2", fetch_redirect_response=False)
        self.car.refresh_from_db()
        self.assertEqual((self.car.name, self.car.color), ("New", "blue"))

    def test_next_url_must_be_local(self):
        r = self.client.post(reverse("car_edit", args=[self.car.id]),
                             {"name": "New", "color": "red", "next": "https://evil.example/"})
        self.assertRedirects(r, reverse("car_list"), fetch_redirect_response=False)

    def test_delete_returns_to_next_page(self):
        r = self.client.post(reverse("car_delete", args=[self.car.id]), {"next": "/?q=old"})
        self.assertRedirects(r, "/?q=old", fetch_redirect_response=False)