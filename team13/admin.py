from django.contrib import admin
from .models import (
    Place,
    PlaceTranslation,
    Event,
    EventTranslation,
    Image,
    Comment,
    HotelDetails,
    RestaurantDetails,
    MuseumDetails,
    PlaceAmenity,
    RouteLog,
)


class PlaceTranslationInline(admin.TabularInline):
    model = PlaceTranslation
    extra = 1


class PlaceAmenityInline(admin.TabularInline):
    model = PlaceAmenity
    extra = 0


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ("place_id", "type", "city", "latitude", "longitude")
    list_filter = ("type", "city")
    search_fields = ("city", "address")
    inlines = [PlaceTranslationInline, PlaceAmenityInline]


@admin.register(PlaceTranslation)
class PlaceTranslationAdmin(admin.ModelAdmin):
    list_display = ("place", "lang", "name")
    list_filter = ("lang",)


class EventTranslationInline(admin.TabularInline):
    model = EventTranslation
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "city", "start_at", "end_at")
    list_filter = ("city",)
    inlines = [EventTranslationInline]


@admin.register(EventTranslation)
class EventTranslationAdmin(admin.ModelAdmin):
    list_display = ("event", "lang", "title")
    list_filter = ("lang",)


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ("image_id", "target_type", "target_id", "image_url")
    list_filter = ("target_type",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("comment_id", "target_type", "target_id", "rating", "created_at")
    list_filter = ("target_type", "rating")


@admin.register(HotelDetails)
class HotelDetailsAdmin(admin.ModelAdmin):
    list_display = ("place", "stars", "price_range")


@admin.register(RestaurantDetails)
class RestaurantDetailsAdmin(admin.ModelAdmin):
    list_display = ("place", "cuisine", "avg_price")


@admin.register(MuseumDetails)
class MuseumDetailsAdmin(admin.ModelAdmin):
    list_display = ("place", "open_at", "close_at", "ticket_price")


@admin.register(PlaceAmenity)
class PlaceAmenityAdmin(admin.ModelAdmin):
    list_display = ("place", "amenity_name")
    list_filter = ("amenity_name",)


@admin.register(RouteLog)
class RouteLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "source_place", "destination_place", "travel_mode", "created_at")
    list_filter = ("travel_mode",)
