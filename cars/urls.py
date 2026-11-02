from django.urls import path
from . import views

urlpatterns = [
    path("", views.car_list, name="car_list"),
    path("cars/new/", views.car_create, name="car_create"),
    path("cars/<int:pk>/edit/", views.car_edit, name="car_edit"),
    path("cars/<int:pk>/delete/", views.car_delete, name="car_delete"),
    path("cars/<int:pk>/move/", views.car_move, name="car_move"),
]
