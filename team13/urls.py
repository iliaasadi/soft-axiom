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
    path("contribution/", views.submit_contribution, name="submit_contribution"),
    path("contribution-image/<str:filename>/", views.serve_contribution_image, name="serve_contribution_image"),
    path("admin/", views.team13_admin_dashboard, name="team13_admin_dashboard"),
    path("admin-panel/", views.team13_admin_dashboard, name="team13_admin_panel"),
    path("admin/approve/<uuid:contribution_id>/", views.team13_admin_approve, name="team13_admin_approve"),
    path("admin/reject/<uuid:contribution_id>/", views.team13_admin_reject, name="team13_admin_reject"),
    path("admin/add-admin/", views.team13_admin_add_admin, name="team13_admin_add_admin"),
]