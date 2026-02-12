"""
خروجی گرفتن از دیتابیس team13 به فایل‌های CSV در team13/temp_data.

پس از هر بارگذاری (run.py یا load_iran_location.py) با فراخوانی این تابع،
داده‌های دیتابیس در پوشه temp_data هم ذخیره می‌شوند (همگام‌سازی).
"""

import csv
from pathlib import Path

# مسیر پیش‌فرض: team13/temp_data نسبت به این فایل
_DEFAULT_TEMP_DATA_DIR = Path(__file__).resolve().parent.parent / "temp_data"
DB = "team13"


def export_team13_to_temp_data(temp_data_dir=None):
    """
    تمام رکوردهای دیتابیس team13 را در پوشه temp_data به صورت CSV می‌نویسد.
    temp_data_dir: مسیر پوشه خروجی؛ پیش‌فرض: team13/temp_data
    """
    from team13.models import (
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

    out_dir = Path(temp_data_dir) if temp_data_dir else _DEFAULT_TEMP_DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) places
    path = out_dir / "places.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["place_id", "type", "city", "address", "latitude", "longitude"])
        for p in Place.objects.using(DB).order_by("place_id"):
            w.writerow([
                str(p.place_id), p.type, p.city or "", p.address or "",
                p.latitude, p.longitude,
            ])

    # 2) place_translations
    path = out_dir / "place_translations.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["place_id", "lang", "name", "description"])
        for t in PlaceTranslation.objects.using(DB).select_related("place").order_by("place_id", "lang"):
            w.writerow([str(t.place_id), t.lang, t.name or "", t.description or ""])

    # 3) events
    path = out_dir / "events.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "start_at", "end_at", "city", "address", "latitude", "longitude"])
        for e in Event.objects.using(DB).order_by("event_id"):
            w.writerow([
                str(e.event_id),
                e.start_at.strftime("%Y-%m-%d %H:%M:%S") if e.start_at else "",
                e.end_at.strftime("%Y-%m-%d %H:%M:%S") if e.end_at else "",
                e.city or "", e.address or "", e.latitude, e.longitude,
            ])

    # 4) event_translations
    path = out_dir / "event_translations.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["event_id", "lang", "title", "description"])
        for t in EventTranslation.objects.using(DB).select_related("event").order_by("event_id", "lang"):
            w.writerow([str(t.event_id), t.lang, t.title or "", t.description or ""])

    # 5) images
    path = out_dir / "images.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image_id", "target_type", "target_id", "image_url"])
        for img in Image.objects.using(DB).order_by("image_id"):
            w.writerow([str(img.image_id), img.target_type, str(img.target_id), img.image_url or ""])

    # 6) comments
    path = out_dir / "comments.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["comment_id", "target_type", "target_id", "rating", "created_at"])
        for c in Comment.objects.using(DB).order_by("comment_id"):
            created = c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else ""
            w.writerow([str(c.comment_id), c.target_type, str(c.target_id), c.rating or "", created])

    # 7) hotel_details
    path = out_dir / "hotel_details.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["place_id", "stars", "price_range"])
        for h in HotelDetails.objects.using(DB).order_by("place_id"):
            w.writerow([str(h.place_id), h.stars or "", h.price_range or ""])

    # 8) restaurant_details
    path = out_dir / "restaurant_details.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["place_id", "cuisine", "avg_price"])
        for r in RestaurantDetails.objects.using(DB).order_by("place_id"):
            w.writerow([str(r.place_id), r.cuisine or "", r.avg_price or ""])

    # 9) museum_details
    path = out_dir / "museum_details.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["place_id", "open_at", "close_at", "ticket_price"])
        for m in MuseumDetails.objects.using(DB).order_by("place_id"):
            open_at = m.open_at.strftime("%H:%M") if m.open_at else ""
            close_at = m.close_at.strftime("%H:%M") if m.close_at else ""
            w.writerow([str(m.place_id), open_at, close_at, m.ticket_price or ""])

    # 10) place_amenities
    path = out_dir / "place_amenities.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["place_id", "amenity_name"])
        for a in PlaceAmenity.objects.using(DB).order_by("place_id", "amenity_name"):
            w.writerow([str(a.place_id), a.amenity_name or ""])

    # 11) route_logs
    path = out_dir / "route_logs.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "user_id", "source_place_id", "destination_place_id", "travel_mode", "created_at"])
        for r in RouteLog.objects.using(DB).select_related("source_place", "destination_place").order_by("id"):
            created = r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
            user_id = str(r.user_id) if r.user_id else ""
            w.writerow([
                getattr(r, "pk", ""),
                user_id,
                str(r.source_place_id),
                str(r.destination_place_id),
                r.travel_mode,
                created,
            ])

    return str(out_dir)
