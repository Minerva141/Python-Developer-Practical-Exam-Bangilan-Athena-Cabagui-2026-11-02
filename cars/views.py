"""Views (the "C" in MVC): thin; ordering logic lives in the model."""
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from urllib.parse import urlencode
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import CarForm
from .models import Car

PAGE_SIZE = 50


def _next_url(request):
    """Where to go after edit/delete: the page the user came from, if safe."""
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return reverse("car_list")


def car_list(request):
    color = request.GET.get("color", "").strip().lower()
    q = request.GET.get("q", "").strip()
    qs = Car.objects.of_color(color).search(q)
    # Searching: best matches first, then the normal list order.
    qs = qs.order_by("match_rank", "position", "id") if q else qs.in_order()
    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get("page"))
    colors = (Car.objects.values("color").annotate(n=Count("id"))
              .order_by("color"))
    # Keeps the active filter/search when clicking Prev/Next.
    base_query = urlencode({k: v for k, v in (("color", color), ("q", q)) if v})
    return render(request, "cars/car_list.html", {
        "page": page, "color": color, "q": q, "colors": colors,
        "base_query": base_query,
    })


def car_create(request):
    form = CarForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()  # appended at the end of the list
        last = Paginator(Car.objects.all(), PAGE_SIZE).num_pages
        return redirect(f"{reverse('car_list')}?page={last}")
    return render(request, "cars/car_form.html", {"form": form, "title": "Add car"})


def car_edit(request, pk):
    car = get_object_or_404(Car, pk=pk)
    form = CarForm(request.POST or None, instance=car)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(_next_url(request))
    return render(request, "cars/car_form.html", {"form": form, "title": f"Edit {car.name}"})


@require_POST
def car_delete(request, pk):
    get_object_or_404(Car, pk=pk).delete()
    return redirect(_next_url(request))


@require_POST
def car_move(request, pk):
    """AJAX: move car in front of ``before`` (id) or after ``after`` (id)."""
    car = get_object_or_404(Car, pk=pk)
    before, after = request.POST.get("before"), request.POST.get("after")
    if before:
        car.move_before(get_object_or_404(Car, pk=before))
    elif after:
        car.move_after(get_object_or_404(Car, pk=after))
    else:
        return JsonResponse({"ok": False, "error": "before or after required"}, status=400)
    return JsonResponse({"ok": True, "position": car.position})