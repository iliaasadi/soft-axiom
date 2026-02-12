from django.urls import path
from . import views

app_name = "team13"

urlpatterns = [
    path("", views.base, name="index"),
    path("ping/", views.ping, name="ping"),
    path("places/", views.place_list, name="place_list"),
    path("places/<uuid:place_id>/", views.place_detail, name="place_detail"),
    path("places/<uuid:place_id>/rate/", views.place_rate, name="place_rate"),
    path("events/", views.event_list, name="event_list"),
    path("events/<uuid:event_id>/", views.event_detail, name="event_detail"),
    path("events/<uuid:event_id>/rate/", views.event_rate, name="event_rate"),
    path("routes/", views.route_request, name="routes"),
    path("emergency/", views.emergency_nearby, name="emergency"),
]