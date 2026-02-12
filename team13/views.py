# مطابق فاز ۳، ۵، ۷ — سرویس امکانات و حمل‌ونقل (گروه Axiom)
import math
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import quote
from django.views.decorators.http import require_GET, require_POST
from core.auth import api_login_required

from .models import (
    Place,
    PlaceTranslation,
    Event,
    EventTranslation,
    RouteLog,
    Comment,
    Image,
)

TEAM_NAME = "team13"


def _wants_json(request):
    """درخواست خروجی JSON (API) دارد یا نه."""
    return (
        request.GET.get("format") == "json"
        or "application/json" in request.headers.get("Accept", "")
    )


def _login_required_team13(view_func):
    """برای درخواست‌های HTML به صفحه ورود با next هدایت می‌کند؛ برای API پاسخ 401."""
    from functools import wraps
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if getattr(request.user, "is_authenticated", False):
            return view_func(request, *args, **kwargs)
        if _wants_json(request):
            return JsonResponse({"detail": "Authentication required"}, status=401)
        login_url = getattr(settings, "LOGIN_URL", "/auth/")
        next_url = request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER") or "/team13/"
        if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts=request.get_host(), require_https=request.is_secure()):
            next_url = "/team13/"
        if "?" in login_url:
            redirect_url = f"{login_url}&next={quote(next_url)}"
        else:
            redirect_url = f"{login_url}?next={quote(next_url)}"
        return redirect(redirect_url)
    return _wrapped


def _distance_km(lat1, lon1, lat2, lon2):
    """فاصله تقریبی به کیلومتر (Haversine)."""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@api_login_required
def ping(request):
    return JsonResponse({"team": TEAM_NAME, "ok": True})


def base(request):
    return render(request, f"{TEAM_NAME}/index.html")


# -----------------------------------------------------------------------------
# مکان‌ها (POI)
# -----------------------------------------------------------------------------

@require_GET
def place_list(request):
    """لیست مکان‌ها با فیلتر نوع و شهر. خروجی: JSON (API) یا صفحه HTML."""
    qs = Place.objects.all().prefetch_related("translations")
    place_type = request.GET.get("type")
    if place_type:
        qs = qs.filter(type=place_type)
    city = request.GET.get("city")
    if city:
        qs = qs.filter(city__icontains=city)
    places_qs = qs[:100]

    places = []
    for p in places_qs:
        trans_fa = p.translations.filter(lang="fa").first()
        trans_en = p.translations.filter(lang="en").first()
        places.append({
            "place_id": str(p.place_id),
            "type": p.type,
            "type_display": p.get_type_display(),
            "city": p.city,
            "address": p.address,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "name_fa": trans_fa.name if trans_fa else "",
            "name_en": trans_en.name if trans_en else "",
        })

    if _wants_json(request):
        return JsonResponse({"places": places})

    return render(request, f"{TEAM_NAME}/places_list.html", {
        "places": places,
        "filter_type": place_type or "",
        "filter_city": city or "",
    })


@require_GET
def place_detail(request, place_id):
    """جزئیات یک مکان با ترجمه‌ها، امکانات، جزئیات تخصصی و نظرات/امتیاز (مطابق فاز ۵)."""
    place = get_object_or_404(
        Place.objects.select_related("hotel_details", "restaurant_details", "museum_details").prefetch_related("translations", "amenities"),
        place_id=place_id,
    )
    trans_fa = place.translations.filter(lang="fa").first()
    trans_en = place.translations.filter(lang="en").first()
    amenities = list(place.amenities.values_list("amenity_name", flat=True))
    comments = list(
        Comment.objects.filter(target_type=Comment.TargetType.PLACE, target_id=place.place_id)
        .order_by("-created_at")[:50]
    )
    images = list(
        Image.objects.filter(target_type=Image.TargetType.PLACE, target_id=place.place_id)
        .values_list("image_url", flat=True)
    )

    detail = {
        "place_id": str(place.place_id),
        "type": place.type,
        "type_display": place.get_type_display(),
        "city": place.city,
        "address": place.address,
        "latitude": place.latitude,
        "longitude": place.longitude,
        "name_fa": trans_fa.name if trans_fa else "",
        "name_en": trans_en.name if trans_en else "",
        "description_fa": trans_fa.description if trans_fa else "",
        "description_en": trans_en.description if trans_en else "",
        "amenities": amenities,
        "comments": comments,
        "images": images,
    }
    if hasattr(place, "hotel_details"):
        detail["hotel"] = {"stars": place.hotel_details.stars, "price_range": place.hotel_details.price_range}
    else:
        detail["hotel"] = None
    if hasattr(place, "restaurant_details"):
        detail["restaurant"] = {"cuisine": place.restaurant_details.cuisine, "avg_price": place.restaurant_details.avg_price}
    else:
        detail["restaurant"] = None
    if hasattr(place, "museum_details"):
        md = place.museum_details
        detail["museum"] = {
            "open_at": str(md.open_at) if md.open_at else None,
            "close_at": str(md.close_at) if md.close_at else None,
            "ticket_price": md.ticket_price,
        }
    else:
        detail["museum"] = None

    if _wants_json(request):
        # خروجی API بدون آبجکت Django
        api = {
            "place_id": detail["place_id"],
            "type": detail["type"],
            "city": detail["city"],
            "address": detail["address"],
            "latitude": detail["latitude"],
            "longitude": detail["longitude"],
            "translations": {"fa": {"name": detail["name_fa"], "description": detail["description_fa"]}, "en": {"name": detail["name_en"], "description": detail["description_en"]}},
            "amenities": detail["amenities"],
            "comments": [{"rating": c.rating, "created_at": c.created_at.isoformat() if c.created_at else None} for c in detail["comments"]],
            "images": detail["images"],
        }
        if detail["hotel"]:
            api["hotel"] = detail["hotel"]
        if detail["restaurant"]:
            api["restaurant"] = detail["restaurant"]
        if detail["museum"]:
            api["museum"] = detail["museum"]
        return JsonResponse(api)

    return render(request, f"{TEAM_NAME}/place_detail.html", {"place": place, "detail": detail})


@require_POST
@_login_required_team13
def place_rate(request, place_id):
    """ثبت امتیاز (۱–۵) برای یک مکان. فقط برای کاربران لاگین‌شده."""
    place = get_object_or_404(Place, place_id=place_id)
    try:
        rating = int(request.POST.get("rating", 0))
        if 1 <= rating <= 5:
            Comment.objects.create(
                target_type=Comment.TargetType.PLACE,
                target_id=place.place_id,
                rating=rating,
            )
    except (ValueError, TypeError):
        pass
    return redirect("team13:place_detail", place_id=place.place_id)


# -----------------------------------------------------------------------------
# رویدادها
# -----------------------------------------------------------------------------

@require_GET
def event_list(request):
    """لیست رویدادها. خروجی: JSON (API) یا صفحه HTML."""
    qs = Event.objects.all().prefetch_related("translations").order_by("-start_at")[:100]
    events = []
    for e in qs:
        trans_fa = e.translations.filter(lang="fa").first()
        trans_en = e.translations.filter(lang="en").first()
        events.append({
            "event_id": str(e.event_id),
            "city": e.city,
            "address": e.address,
            "start_at": e.start_at,
            "end_at": e.end_at,
            "start_at_iso": e.start_at.isoformat(),
            "end_at_iso": e.end_at.isoformat(),
            "title_fa": trans_fa.title if trans_fa else "",
            "title_en": trans_en.title if trans_en else "",
            "description_fa": trans_fa.description if trans_fa else "",
        })

    if _wants_json(request):
        return JsonResponse({
            "events": [
                {
                    "event_id": x["event_id"],
                    "city": x["city"],
                    "start_at": x["start_at_iso"],
                    "end_at": x["end_at_iso"],
                    "title_fa": x["title_fa"],
                }
                for x in events
            ]
        })

    return render(request, f"{TEAM_NAME}/events_list.html", {"events": events})


@require_GET
def event_detail(request, event_id):
    """جزئیات یک رویداد با ترجمه‌ها و نظرات/امتیاز."""
    event = get_object_or_404(
        Event.objects.prefetch_related("translations"),
        event_id=event_id,
    )
    trans_fa = event.translations.filter(lang="fa").first()
    trans_en = event.translations.filter(lang="en").first()
    comments = list(
        Comment.objects.filter(target_type=Comment.TargetType.EVENT, target_id=event.event_id)
        .order_by("-created_at")[:50]
    )
    images = list(
        Image.objects.filter(target_type=Image.TargetType.EVENT, target_id=event.event_id)
        .values_list("image_url", flat=True)
    )

    detail = {
        "event_id": str(event.event_id),
        "city": event.city,
        "address": event.address,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "start_at": event.start_at,
        "end_at": event.end_at,
        "title_fa": trans_fa.title if trans_fa else "",
        "title_en": trans_en.title if trans_en else "",
        "description_fa": trans_fa.description if trans_fa else "",
        "description_en": trans_en.description if trans_en else "",
        "comments": comments,
        "images": images,
    }

    if _wants_json(request):
        return JsonResponse({
            **detail,
            "start_at": event.start_at.isoformat(),
            "end_at": event.end_at.isoformat(),
            "comments": [{"rating": c.rating, "created_at": c.created_at.isoformat() if c.created_at else None} for c in comments],
        })

    return render(request, f"{TEAM_NAME}/event_detail.html", {"event": event, "detail": detail})


@require_POST
@_login_required_team13
def event_rate(request, event_id):
    """ثبت امتیاز (۱–۵) برای یک رویداد. فقط برای کاربران لاگین‌شده."""
    event = get_object_or_404(Event, event_id=event_id)
    try:
        rating = int(request.POST.get("rating", 0))
        if 1 <= rating <= 5:
            Comment.objects.create(
                target_type=Comment.TargetType.EVENT,
                target_id=event.event_id,
                rating=rating,
            )
    except (ValueError, TypeError):
        pass
    return redirect("team13:event_detail", event_id=event.event_id)


# -----------------------------------------------------------------------------
# مسیریابی و امکانات روی مسیر (مرحله ۴: اتصال به API نقشه Map.ir برای ETA)
# -----------------------------------------------------------------------------

def _compute_route_result(source, dest, travel_mode, request):
    """محاسبه فاصله و ETA؛ در حالت خودرو در صورت وجود کلید Map.ir از API ETA استفاده می‌کند."""
    from .mapir_eta import fetch_route_eta

    dist_km = _distance_km(source.latitude, source.longitude, dest.latitude, dest.longitude)
    eta_minutes = None
    eta_source = "haversine"

    if travel_mode == "car":
        dist_mapir, dur_sec = fetch_route_eta(
            source.longitude, source.latitude,
            dest.longitude, dest.latitude,
        )
        if dist_mapir is not None and dur_sec is not None:
            dist_km = dist_mapir
            eta_minutes = max(1, round(dur_sec / 60.0))
            eta_source = "mapir"
        else:
            eta_minutes = max(1, round(dist_km / 0.5))
    elif travel_mode == "walk":
        eta_minutes = max(1, round(dist_km / 0.08))
    else:
        eta_minutes = max(1, round(dist_km / 0.4))

    trans_src = source.translations.filter(lang="fa").first()
    trans_dst = dest.translations.filter(lang="fa").first()
    return {
        "source_place_id": str(source.place_id),
        "destination_place_id": str(dest.place_id),
        "source_name": trans_src.name if trans_src else str(source.place_id),
        "destination_name": trans_dst.name if trans_dst else str(dest.place_id),
        "travel_mode": travel_mode,
        "distance_km": round(dist_km, 2),
        "eta_minutes": eta_minutes,
        "eta_source": eta_source,
        "source_amenities": list(source.amenities.values_list("amenity_name", flat=True)),
        "destination_amenities": list(dest.amenities.values_list("amenity_name", flat=True)),
    }


@require_GET
def route_request(request):
    """
    مسیریابی و ETA بین دو مکان + امکانات مبدأ و مقصد.
    برای حالت خودرو در صورت تنظیم MAPIR_API_KEY از API تخمین زمان رسیدن مپ استفاده می‌شود.
    """
    src_id = request.GET.get("source_place_id")
    dst_id = request.GET.get("destination_place_id")
    travel_mode = request.GET.get("travel_mode", "car").lower()
    if travel_mode not in ("car", "walk", "transit"):
        travel_mode = "car"

    if _wants_json(request):
        if not src_id or not dst_id:
            return JsonResponse({"error": "source_place_id و destination_place_id الزامی است"}, status=400)
        try:
            source = Place.objects.prefetch_related("translations", "amenities").get(place_id=src_id)
            dest = Place.objects.prefetch_related("translations", "amenities").get(place_id=dst_id)
        except Place.DoesNotExist:
            return JsonResponse({"error": "مکان مبدأ یا مقصد یافت نشد"}, status=404)
        result = _compute_route_result(source, dest, travel_mode, request)
        if getattr(request.user, "is_authenticated", False):
            try:
                RouteLog.objects.create(
                    user_id=getattr(request.user, "id", None),
                    source_place=source,
                    destination_place=dest,
                    travel_mode=travel_mode,
                )
            except Exception:
                pass
        return JsonResponse(result)

    # صفحه HTML: فرم انتخاب مبدأ و مقصد و نمایش نتیجه + امکانات
    route_result = None
    if src_id and dst_id:
        try:
            source = Place.objects.prefetch_related("translations", "amenities").get(place_id=src_id)
            dest = Place.objects.prefetch_related("translations", "amenities").get(place_id=dst_id)
            route_result = _compute_route_result(source, dest, travel_mode, request)
            if getattr(request.user, "is_authenticated", False):
                try:
                    RouteLog.objects.create(
                        user_id=getattr(request.user, "id", None),
                        source_place=source,
                        destination_place=dest,
                        travel_mode=travel_mode,
                    )
                except Exception:
                    pass
        except Place.DoesNotExist:
            route_result = {"error": "مکان مبدأ یا مقصد یافت نشد."}

    # لیست مکان‌ها برای dropdown
    places_choices = list(Place.objects.all().prefetch_related("translations")[:200])
    places_for_select = []
    for p in places_choices:
        t = p.translations.filter(lang="fa").first()
        name = (t.name if t else None) or (p.translations.filter(lang="en").first().name if p.translations.filter(lang="en").first() else None) or str(p.place_id)
        places_for_select.append({"place_id": str(p.place_id), "name": name})

    return render(request, f"{TEAM_NAME}/routes.html", {
        "route_result": route_result,
        "places_for_select": places_for_select,
        "travel_mode": travel_mode,
        "source_place_id": src_id or "",
        "destination_place_id": dst_id or "",
    })


# -----------------------------------------------------------------------------
# حالت اضطراری — مراکز امدادی نزدیک
# -----------------------------------------------------------------------------

@require_GET
def emergency_nearby(request):
    """
    نزدیک‌ترین مراکز امدادی (بیمارستان) به موقعیت.
    از دیتابیس team13 استفاده می‌کند؛ در صورت تنظیم MAPIR_API_KEY، نتایج Map.ir (Places API)
    هم ادغام می‌شوند تا پوشش بهتری داشته باشیم.
    GET با lat, lon: خروجی JSON یا صفحه HTML با لیست.
    """
    try:
        lat = float(request.GET.get("lat", 35.6892))
        lon = float(request.GET.get("lon", 51.3890))
    except ValueError:
        lat, lon = 35.6892, 51.3890
    limit = min(20, max(1, int(request.GET.get("limit", 10))))

    # از دیتابیس: بیمارستان‌های ذخیره‌شده
    hospitals = list(
        Place.objects.filter(type=Place.PlaceType.HOSPITAL)
        .prefetch_related("translations")[:100]
    )
    with_dist = []
    for p in hospitals:
        d = _distance_km(lat, lon, p.latitude, p.longitude)
        trans_fa = p.translations.filter(lang="fa").first()
        with_dist.append({
            "place_id": str(p.place_id),
            "name_fa": trans_fa.name if trans_fa else "",
            "address": p.address,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "distance_km": round(d, 2),
            "eta_minutes": max(1, round(d / 0.5)),
            "source": "db",
        })
    with_dist.sort(key=lambda x: x["distance_km"])

    # در صورت وجود کلید Map.ir، مراکز امدادی از API مکان‌های مپ هم گرفته می‌شود و ادغام می‌شوند
    try:
        from .mapir_places import emergency_places_from_mapir, get_mapir_api_key
        if get_mapir_api_key():
            mapir_list = emergency_places_from_mapir(lat, lon, limit=limit)
            # ادغام: ابتدا از DB، سپس از Map.ir (بدون تکرار بر اساس فاصله و نام نزدیک)
            seen_keys = {(round(x["latitude"], 5), round(x["longitude"], 5)) for x in with_dist[:limit]}
            for item in mapir_list:
                key = (round(item["latitude"], 5), round(item["longitude"], 5))
                if key not in seen_keys:
                    seen_keys.add(key)
                    with_dist.append(item)
            with_dist.sort(key=lambda x: x["distance_km"])
    except Exception:
        pass

    emergency_places = with_dist[:limit]

    if _wants_json(request):
        return JsonResponse({"emergency_places": emergency_places})

    return render(request, f"{TEAM_NAME}/emergency.html", {
        "emergency_places": emergency_places,
        "lat": lat,
        "lon": lon,
    })
