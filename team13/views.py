# مطابق فاز ۳، ۵، ۷ — سرویس امکانات و حمل‌ونقل (گروه Axiom)
import base64
import math
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import quote
from django.db.models import Avg, Q, Subquery, OuterRef
from django.db.models.functions import Coalesce
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
    PlaceContribution,
    TeamAdmin,
)

# پوشه ذخیره تصاویر پیشنهاد مکان (بدون استفاده از MEDIA_ROOT سراسری)
CONTRIBUTION_UPLOAD_DIR = Path(__file__).resolve().parent / "contribution_uploads"

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

def _parse_lat_lng(request):
    """Parse lat/lng from GET; return (lat, lng) or (None, None) if invalid/missing."""
    lat_s = request.GET.get("lat")
    lng_s = request.GET.get("lng")
    if lat_s is None or lng_s is None:
        return None, None
    try:
        lat = float(lat_s)
        lng = float(lng_s)
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return None, None
        return lat, lng
    except (TypeError, ValueError):
        return None, None


def _apply_price_level_filter(qs, price_level):
    """Filter queryset by price_level (Pricing): 1=budget, 2=mid, 3=high. Applies to hotels (stars) and restaurants (avg_price); other types are included."""
    if not price_level:
        return qs
    level = str(price_level).strip()
    other_types = [Place.PlaceType.MUSEUM, Place.PlaceType.ENTERTAINMENT, Place.PlaceType.HOSPITAL]
    if level == "1":
        qs = qs.filter(
            Q(type=Place.PlaceType.HOTEL, hotel_details__stars__lte=2)
            | Q(type=Place.PlaceType.FOOD, restaurant_details__avg_price__lte=200000)
            | Q(type__in=other_types)
        )
    elif level == "2":
        qs = qs.filter(
            Q(type=Place.PlaceType.HOTEL, hotel_details__stars=3)
            | Q(
                type=Place.PlaceType.FOOD,
                restaurant_details__avg_price__gt=200000,
                restaurant_details__avg_price__lte=500000,
            )
            | Q(type__in=other_types)
        )
    elif level == "3":
        qs = qs.filter(
            Q(type=Place.PlaceType.HOTEL, hotel_details__stars__gte=4)
            | Q(type=Place.PlaceType.FOOD, restaurant_details__avg_price__gt=500000)
            | Q(type__in=other_types)
        )
    return qs


@require_GET
def place_list(request):
    """لیست مکان‌ها (Top 10 بر اساس امتیاز)، فیلتر نوع/شهر/قیمت، و فاصله Haversine در صورت ارسال lat/lng."""
    # Subquery: average rating (stars) per place from Comment
    rating_subq = (
        Comment.objects.filter(
            target_type=Comment.TargetType.PLACE,
            target_id=OuterRef("place_id"),
        )
        .values("target_id")
        .annotate(avg_rating=Avg("rating"))
        .values("avg_rating")
    )
    qs = (
        Place.objects.all()
        .select_related("hotel_details", "restaurant_details")
        .prefetch_related("translations")
        .annotate(avg_stars=Coalesce(Subquery(rating_subq), 0.0))
        .order_by("-avg_stars")
    )
    # Category (Type): type or category GET param
    place_type = request.GET.get("type") or request.GET.get("category")
    if place_type and place_type in dict(Place.PlaceType.choices):
        qs = qs.filter(type=place_type)
    city = request.GET.get("city")
    if city:
        qs = qs.filter(city__icontains=city)
    # Pricing filter
    price_level = request.GET.get("price_level")
    qs = _apply_price_level_filter(qs, price_level)
    # Rating filter (minimum stars)
    min_rating = request.GET.get("min_rating")
    if min_rating is not None:
        try:
            r = float(min_rating)
            if 1 <= r <= 5:
                qs = qs.filter(avg_stars__gte=r)
        except (TypeError, ValueError):
            pass
    # Top 10 by stars (fetch more when distance filter will be applied)
    max_distance = request.GET.get("max_distance")
    try:
        max_dist_km = float(max_distance) if max_distance else None
    except (TypeError, ValueError):
        max_dist_km = None
    places_qs = list(qs[:50] if max_dist_km else qs[:10])
    place_ids = [p.place_id for p in places_qs]
    rating_rows = (
        Comment.objects.filter(
            target_type=Comment.TargetType.PLACE,
            target_id__in=place_ids,
        )
        .values("target_id")
        .annotate(avg_rating=Avg("rating"))
    )
    rating_by_place = {str(r["target_id"]): round(float(r["avg_rating"]), 1) for r in rating_rows}

    user_lat, user_lng = _parse_lat_lng(request)
    places = []
    for p in places_qs:
        trans_fa = p.translations.filter(lang="fa").first()
        trans_en = p.translations.filter(lang="en").first()
        item = {
            "place_id": str(p.place_id),
            "type": p.type,
            "type_display": p.get_type_display(),
            "city": p.city,
            "address": p.address,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "name_fa": trans_fa.name if trans_fa else "",
            "name_en": trans_en.name if trans_en else "",
            "rating": rating_by_place.get(str(p.place_id)),
        }
        if user_lat is not None and user_lng is not None:
            item["distance_km"] = round(_distance_km(user_lat, user_lng, p.latitude, p.longitude), 2)
        places.append(item)

    # Distance filter (when lat/lng present): keep only places within max_distance_km
    if max_dist_km is not None and user_lat is not None and user_lng is not None:
        places = [item for item in places if item.get("distance_km") is not None and item["distance_km"] <= max_dist_km]
    places = places[:10]

    if _wants_json(request):
        return JsonResponse({"places": places})

    return render(request, f"{TEAM_NAME}/places_list.html", {
        "places": places,
        "filter_type": place_type or "",
        "filter_city": city or "",
        "filter_min_rating": request.GET.get("min_rating") or "",
        "filter_price_level": request.GET.get("price_level") or "",
        "filter_max_distance": request.GET.get("max_distance") or "",
        "current_lat": user_lat,
        "current_lng": user_lng,
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
# پیشنهاد مکان (Place Contribution)
# -----------------------------------------------------------------------------

def _save_contribution_image(upload_dir, file_content, ext=".jpg"):
    """ذخیره بایت‌های تصویر در upload_dir و برگرداندن نام فایل امن برای URL."""
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}{ext}"
    path = upload_dir / safe_name
    path.write_bytes(file_content)
    return safe_name


@require_GET
def serve_contribution_image(request, filename):
    """سرو تصویر آپلود شده پیشنهاد مکان (فقط نام فایل امن)."""
    if not re.match(r"^[a-zA-Z0-9_.-]+$", filename) or ".." in filename:
        raise Http404("Invalid filename")
    path = CONTRIBUTION_UPLOAD_DIR / filename
    if not path.is_file():
        raise Http404("Not found")
    content_type = "image/jpeg"
    if filename.lower().endswith(".png"):
        content_type = "image/png"
    elif filename.lower().endswith(".gif"):
        content_type = "image/gif"
    elif filename.lower().endswith(".webp"):
        content_type = "image/webp"
    return FileResponse(path.open("rb"), content_type=content_type)


@require_POST
@_login_required_team13
def submit_contribution(request):
    """
    ثبت پیشنهاد مکان: name_fa, name_en (اختیاری), type, address (اختیاری),
    latitude, longitude؛ و تصویر به صورت multipart (image) یا base64 (image_base64).
    """
    name_fa = (request.POST.get("name_fa") or "").strip()
    if not name_fa:
        if _wants_json(request):
            return JsonResponse({"error": "نام مکان (name_fa) الزامی است."}, status=400)
        return JsonResponse({"error": "نام مکان (name_fa) الزامی است."}, status=400)
    name_en = (request.POST.get("name_en") or "").strip()
    place_type = (request.POST.get("type") or "").strip()
    if place_type not in dict(Place.PlaceType.choices):
        place_type = Place.PlaceType.FOOD
    address = (request.POST.get("address") or "").strip()
    try:
        lat = float(request.POST.get("latitude", 0))
        lng = float(request.POST.get("longitude", 0))
    except (TypeError, ValueError):
        lat, lng = 0.0, 0.0
    city = (request.POST.get("city") or "").strip()

    contribution = PlaceContribution.objects.create(
        name_fa=name_fa,
        name_en=name_en or name_fa,
        type=place_type,
        address=address,
        latitude=lat,
        longitude=lng,
        city=city,
        submitted_by_id=getattr(request.user, "id", None),
    )
    image_url = None
    # 1) فایل آپلود شده (multipart)
    if request.FILES and request.FILES.get("image"):
        f = request.FILES["image"]
        ext = Path(f.name).suffix if getattr(f, "name", None) else ".jpg"
        if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            ext = ".jpg"
        content = f.read()
        safe_name = _save_contribution_image(CONTRIBUTION_UPLOAD_DIR, content, ext)
        image_url = request.build_absolute_uri(reverse("team13:serve_contribution_image", args=[safe_name]))
    # 2) تصویر base64 (مثلاً اگر آپلود فایل در دسترس نباشد)
    elif request.POST.get("image_base64"):
        raw = request.POST.get("image_base64", "")
        if raw.startswith("data:"):
            raw = raw.split(",", 1)[-1]
        try:
            content = base64.b64decode(raw)
        except Exception:
            content = None
        if content and len(content) < 10 * 1024 * 1024:  # حداکثر 10MB
            ext = ".jpg"
            if request.POST.get("image_mimetype", "").strip().startswith("image/png"):
                ext = ".png"
            elif request.POST.get("image_mimetype", "").strip().startswith("image/gif"):
                ext = ".gif"
            elif request.POST.get("image_mimetype", "").strip().startswith("image/webp"):
                ext = ".webp"
            safe_name = _save_contribution_image(CONTRIBUTION_UPLOAD_DIR, content, ext)
            image_url = request.build_absolute_uri(reverse("team13:serve_contribution_image", args=[safe_name]))
    if image_url:
        Image.objects.create(
            target_type=Image.TargetType.PENDING_PLACE,
            target_id=contribution.contribution_id,
            image_url=image_url,
        )
    if _wants_json(request):
        return JsonResponse({
            "ok": True,
            "contribution_id": str(contribution.contribution_id),
            "message": "پیشنهاد مکان با موفقیت ثبت شد و پس از تأیید در نقشه نمایش داده می‌شود.",
        })
    return JsonResponse({
        "ok": True,
        "contribution_id": str(contribution.contribution_id),
        "message": "پیشنهاد مکان با موفقیت ثبت شد.",
    })


# -----------------------------------------------------------------------------
# پنل ادمین تیم ۱۳ (فقط برای کاربران TeamAdmin)
# -----------------------------------------------------------------------------

def is_team13_admin(user):
    """بررسی اینکه کاربر در جدول TeamAdmin باشد یا سوپریوزر باشد."""
    if not getattr(user, "is_authenticated", False):
        return False
    return (
        TeamAdmin.objects.using("team13").filter(user_id=str(user.id)).exists()
        or getattr(user, "is_superuser", False)
    )


def _is_team13_admin(user):
    """Alias for is_team13_admin (backward compatibility)."""
    return is_team13_admin(user)


def team13_admin_dashboard(request):
    """داشبورد ادمین: لیست پیشنهادهای در انتظار تأیید و مدیریت ادمین‌ها."""
    if not getattr(request.user, "is_authenticated", False):
        return redirect(getattr(settings, "LOGIN_URL", "/auth/") + "?next=" + quote(request.get_full_path()))
    if not is_team13_admin(request.user):
        login_url = getattr(settings, "LOGIN_URL", "/auth/")
        next_url = quote(request.get_full_path())
        return HttpResponseForbidden(
            '<h1>403 Forbidden</h1><p>دسترسی به پنل ادمین تیم ۱۳ مجاز نیست.</p>'
            '<p><a href="' + login_url + '?next=' + next_url + '" style="display:inline-block;margin-top:12px;padding:10px 20px;background:#1b4332;color:#fff;border-radius:8px;text-decoration:none;">ورود (Login)</a></p>'
        )

    # پیشنهادهای در انتظار (pending = is_approved=False) از دیتابیس team13
    pending = PlaceContribution.objects.using("team13").filter(is_approved=False).order_by("-created_at")
    pending_requests = []
    for c in pending:
        images = list(
            Image.objects.using("team13").filter(
                target_type=Image.TargetType.PENDING_PLACE,
                target_id=c.contribution_id,
            ).values_list("image_url", flat=True)
        )
        map_url = (
            reverse("team13:index")
            + "?lat={}&lng={}&zoom=16".format(c.latitude, c.longitude)
        )
        submitter_display = "—"
        if c.submitted_by_id:
            try:
                User = request.user.__class__
                sub = User.objects.using("default").filter(id=c.submitted_by_id).first()
                submitter_display = getattr(sub, "email", str(c.submitted_by_id)) if sub else str(c.submitted_by_id)
            except Exception:
                submitter_display = str(c.submitted_by_id)
        pending_requests.append({
            "contribution": c,
            "images": images,
            "map_url": map_url,
            "submitter_display": submitter_display,
        })

    return render(request, f"{TEAM_NAME}/admin_dashboard.html", {
        "pending_requests": pending_requests,
        "contributions_with_images": pending_requests,
        "map_index_url": reverse("team13:index"),
    })


@require_POST
def team13_admin_approve(request, contribution_id):
    """تأیید یک پیشنهاد مکان (فقط ادمین)."""
    if not getattr(request.user, "is_authenticated", False):
        return HttpResponseForbidden("Authentication required")
    if not is_team13_admin(request.user):
        return HttpResponseForbidden("Forbidden")
    from .moderation import approve_contribution
    try:
        approve_contribution(contribution_id)
    except PlaceContribution.DoesNotExist:
        pass
    return redirect("team13:team13_admin_panel")


@require_POST
def team13_admin_reject(request, contribution_id):
    """رد یک پیشنهاد مکان و حذف آن (فقط ادمین)."""
    if not getattr(request.user, "is_authenticated", False):
        return HttpResponseForbidden("Authentication required")
    if not is_team13_admin(request.user):
        return HttpResponseForbidden("Forbidden")
    contribution = PlaceContribution.objects.using("team13").filter(contribution_id=contribution_id).first()
    if contribution:
        Image.objects.using("team13").filter(
            target_type=Image.TargetType.PENDING_PLACE,
            target_id=contribution.contribution_id,
        ).delete()
        contribution.delete()
    return redirect("team13:team13_admin_panel")


@require_POST
def team13_admin_add_admin(request):
    """افزودن کاربر به جدول ادمین‌ها با ایمیل (فقط ادمین فعلی)."""
    if not getattr(request.user, "is_authenticated", False):
        return HttpResponseForbidden("Authentication required")
    if not is_team13_admin(request.user):
        return HttpResponseForbidden("Forbidden")
    User = request.user.__class__
    email = (request.POST.get("email") or "").strip().lower()
    if not email:
        return redirect("team13:team13_admin_panel")
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return redirect("team13:team13_admin_panel")
    TeamAdmin.objects.using("team13").get_or_create(
        user_id=str(user.id),
        defaults={"user_id": str(user.id)},
    )
    return redirect("team13:team13_admin_panel")


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
            "latitude": e.latitude,
            "longitude": e.longitude,
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
                    "latitude": x.get("latitude"),
                    "longitude": x.get("longitude"),
                    "start_at": x["start_at_iso"],
                    "end_at": x.get("end_at_iso"),
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
        "source_lat": source.latitude,
        "source_lng": source.longitude,
        "dest_lat": dest.latitude,
        "dest_lng": dest.longitude,
    }


def _compute_route_result_from_coords(lat_src, lng_src, name_src, lat_dest, lng_dest, name_dest, travel_mode):
    """محاسبه فاصله و ETA از روی مختصات (برای جستجوی آدرس)."""
    from .mapir_eta import fetch_route_eta

    dist_km = _distance_km(lat_src, lng_src, lat_dest, lng_dest)
    eta_minutes = None
    eta_source = "haversine"

    if travel_mode == "car":
        dist_mapir, dur_sec = fetch_route_eta(lng_src, lat_src, lng_dest, lat_dest)
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

    return {
        "source_name": name_src or "مبدأ",
        "destination_name": name_dest or "مقصد",
        "travel_mode": travel_mode,
        "distance_km": round(dist_km, 2),
        "eta_minutes": eta_minutes,
        "eta_source": eta_source,
        "source_amenities": [],
        "destination_amenities": [],
        "source_lat": lat_src,
        "source_lng": lng_src,
        "dest_lat": lat_dest,
        "dest_lng": lng_dest,
    }


@require_GET
def route_request(request):
    """
    مسیریابی و ETA بین دو مکان + امکانات مبدأ و مقصد.
    پذیرش: source_place_id/destination_place_id (مکان از دیتابیس) یا
    source_lat, source_lng, source_name, dest_lat, dest_lng, dest_name (جستجوی آدرس).
    """
    src_id = request.GET.get("source_place_id")
    dst_id = request.GET.get("destination_place_id")
    source_lat = request.GET.get("source_lat")
    source_lng = request.GET.get("source_lng")
    source_name = request.GET.get("source_name", "")
    dest_lat = request.GET.get("dest_lat")
    dest_lng = request.GET.get("dest_lng")
    dest_name = request.GET.get("dest_name", "")
    travel_mode = request.GET.get("travel_mode", "car").lower()
    if travel_mode not in ("car", "walk", "transit"):
        travel_mode = "car"

    if _wants_json(request):
        if src_id and dst_id:
            try:
                source = Place.objects.prefetch_related("translations", "amenities").get(place_id=src_id)
                dest = Place.objects.prefetch_related("translations", "amenities").get(place_id=dst_id)
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
            except Place.DoesNotExist:
                return JsonResponse({"error": "مکان مبدأ یا مقصد یافت نشد"}, status=404)
        if source_lat and source_lng and dest_lat and dest_lng:
            try:
                lat_s = float(source_lat)
                lng_s = float(source_lng)
                lat_d = float(dest_lat)
                lng_d = float(dest_lng)
                result = _compute_route_result_from_coords(
                    lat_s, lng_s, source_name, lat_d, lng_d, dest_name, travel_mode
                )
                return JsonResponse(result)
            except (TypeError, ValueError):
                pass
        return JsonResponse({"error": "source_place_id و destination_place_id یا source_lat/lng و dest_lat/lng الزامی است"}, status=400)

    # صفحه HTML
    route_result = None
    if source_lat and source_lng and dest_lat and dest_lng:
        try:
            lat_s = float(source_lat)
            lng_s = float(source_lng)
            lat_d = float(dest_lat)
            lng_d = float(dest_lng)
            route_result = _compute_route_result_from_coords(
                lat_s, lng_s, source_name, lat_d, lng_d, dest_name, travel_mode
            )
        except (TypeError, ValueError):
            route_result = {"error": "مختصات مبدأ یا مقصد نامعتبر است."}
    elif src_id and dst_id:
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
