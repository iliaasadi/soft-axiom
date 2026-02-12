"""
بارگذاری دادهٔ مکان‌ها (POI) از API نقشه (Map.ir) به دیتابیس team13.

مطابق ساختار دیتابیس: Place، PlaceTranslation، HotelDetails، RestaurantDetails،
MuseumDetails، PlaceAmenity. از API_KEY (متغیر محیطی) استفاده می‌کند.

اجرا از ریشهٔ پروژه:
  set MAPIR_API_KEY=your_key
  py -3.11 team13/get_data/run.py
یا:
  py -3.11 manage.py shell
  exec(open("team13/get_data/run.py", encoding="utf-8").read())
"""

import json
import logging
import math
import os
import random
import sys
import time
from pathlib import Path

# اضافه کردن ریشهٔ پروژه به path تا app404 و team13 قابل import باشند
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import requests

# راه‌اندازی Django برای استفاده از مدل‌ها و دیتابیس team13
if os.environ.get("DJANGO_SETTINGS_MODULE") is None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app404.settings")
import django
django.setup()

from team13.models import (
    Place,
    PlaceTranslation,
    HotelDetails,
    RestaurantDetails,
    MuseumDetails,
    PlaceAmenity,
)

# =============================================================================
# تنظیمات
# =============================================================================

# کلید API: اول از متغیر محیطی MAPIR_API_KEY یا API_KEY؛ در غیر این صورت از مقدار زیر استفاده می‌شود.
API_KEY = (
    os.environ.get("MAPIR_API_KEY")
    or os.environ.get("API_KEY")
    or "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjUxNDFhMWMzNmMzYWEwYjRkMTAzODNjNmRmYTNlNGIwNzc4NzY3ZDUyNzZmYTdhNjY0NDIxMzM0YTZkZmU0ZWZjNmIyOTRlODZmZDc4NWNmIn0.eyJhdWQiOiIzNzAxNCIsImp0aSI6IjUxNDFhMWMzNmMzYWEwYjRkMTAzODNjNmRmYTNlNGIwNzc4NzY3ZDUyNzZmYTdhNjY0NDIxMzM0YTZkZmU0ZWZjNmIyOTRlODZmZDc4NWNmIiwiaWF0IjoxNzcwODM5NzU3LCJuYmYiOjE3NzA4Mzk3NTcsImV4cCI6MTc3MzM0NTM1Nywic3ViIjoiIiwic2NvcGVzIjpbImJhc2ljIl19.mXTXTDqNxPmHaQ6Mgl5Kj5VWDJUiMN2c_zX7TSGERlocEg2Do1_IDLo537e5rN2LzYQXDuNkOSagRE_bbwTdWU6ZD6lT0amYhht00if0-rOe7W6V3_Y4-PiT-HAZQoZtm9G8jvClV21VttLfsv27VAHdQ_Q1Q7xWR5gV-XjNVSgDVQi4tphHTBSBYl-AwOQYnk-lYdGKc9QUXy9e9TOrx7yDUhccv8C21kIex0f3mhbVnVzMXZsl-TbQ1djIH6qVs8KVg_lEweI2sDZx7_R2GeeXccPU3tEXAgjSQy_ZK6hRDRTZ-OcgzRyRPuNAAjIiIP1jufCZ4IY7lkL_OddCpw"
)
if not API_KEY:
    raise ValueError("کلید API (MAPIR_API_KEY یا API_KEY) تنظیم نشده است.")

BASE_URL = "https://map.ir/places"
HEADERS = {"x-api-key": API_KEY}
BUFFER_METERS = 15000
TOP_PER_PAGE = 20
REQUEST_TIMEOUT = 15
RETRIES = 3
BACKOFF_BASE = 1.5
SLEEP_BETWEEN_PAGES = 0.3

# مسیر فایل شهرها (همان ساختار دیتابیس/پروژه)
SCRIPT_DIR = Path(__file__).resolve().parent
CITIES_JSON = SCRIPT_DIR / "iran_location" / "cities.json"

# نگاشت زیردسته Map.ir به نوع مکان در دیتابیس (Place.type)
# مدل ما: hotel, food, museum, hospital, entertainment
SUBCATEGORY_TO_PLACE_TYPE = {
    "hotel": Place.PlaceType.HOTEL,
    "hospital": Place.PlaceType.HOSPITAL,
    "restaurant": Place.PlaceType.FOOD,
    "clinic": Place.PlaceType.HOSPITAL,
    "chemist_and_pharmacy": Place.PlaceType.HOSPITAL,
    "museum": Place.PlaceType.MUSEUM,
}

SUBCATEGORIES = list(SUBCATEGORY_TO_PLACE_TYPE.keys())

# لاگ
LOG_DIR = SCRIPT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "mapir_to_db.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("mapir_to_db")

DB = "team13"


# =============================================================================
# توابع کمکی
# =============================================================================

def safe_request(method, url, headers=None, params=None):
    """درخواست HTTP با تلاش مجدد و پس‌زنی تصاعدی."""
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 200:
                return resp
            logger.warning("HTTP %s | attempt %s/%s | %s", resp.status_code, attempt, RETRIES, url)
        except requests.exceptions.RequestException as e:
            logger.warning("Request error | attempt %s/%s | %s", attempt, RETRIES, e)
        time.sleep(BACKOFF_BASE ** attempt + random.uniform(0, 0.5))
    logger.error("FAILED after %s retries | %s", RETRIES, url)
    return None


def load_cities():
    """بارگذاری لیست شهرها از iran_location/cities.json."""
    if not CITIES_JSON.exists():
        raise FileNotFoundError(f"فایل شهرها یافت نشد: {CITIES_JSON}")
    with open(CITIES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    # ساختار: [ { "city_id", "name_fa", "name_en", "province", "location": { "latitude", "longitude" } }, ... ]
    cities = []
    for item in data:
        loc = item.get("location") or {}
        cities.append({
            "city": item.get("name_fa") or item.get("name_en") or "",
            "lat": loc.get("latitude"),
            "lon": loc.get("longitude"),
        })
    cities = [c for c in cities if c["lat"] is not None and c["lon"] is not None and c["city"]]
    logger.info("تعداد شهرها: %s", len(cities))
    return cities


def ensure_place_and_translation(place_type, city, address, latitude, longitude, name_fa, name_en=None):
    """
    در صورت نبودن مکان با همین مختصات و نام، ایجاد Place و PlaceTranslation (fa و در صورت وجود en).
    برگرداندن (place, created).
    """
    existing = Place.objects.using(DB).filter(
        type=place_type,
        latitude=latitude,
        longitude=longitude,
        city=city,
    ).first()
    if existing:
        return existing, False
    place = Place.objects.using(DB).create(
        type=place_type,
        city=city or "",
        address=address or "",
        latitude=float(latitude),
        longitude=float(longitude),
    )
    PlaceTranslation.objects.using(DB).create(
        place=place,
        lang="fa",
        name=name_fa or "بدون نام",
        description="",
    )
    if name_en:
        PlaceTranslation.objects.using(DB).get_or_create(
            place=place,
            lang="en",
            defaults={"name": name_en, "description": ""},
        )
    return place, True


def create_detail_tables(place, subcategory, item):
    """بر اساس نوع مکان، رکورد در HotelDetails / RestaurantDetails / MuseumDetails ایجاد کن."""
    if subcategory == "hotel":
        if not hasattr(place, "hotel_details"):
            HotelDetails.objects.using(DB).create(
                place=place,
                stars=None,
                price_range=item.get("price_range") or "",
            )
    elif subcategory == "restaurant":
        if not hasattr(place, "restaurant_details"):
            RestaurantDetails.objects.using(DB).create(
                place=place,
                cuisine=item.get("cuisine") or "ایرانی",
                avg_price=None,
            )
    elif subcategory == "museum":
        if not hasattr(place, "museum_details"):
            MuseumDetails.objects.using(DB).create(
                place=place,
                open_at=None,
                close_at=None,
                ticket_price=None,
            )


# =============================================================================
# اصلی
# =============================================================================

def main():
    cities = load_cities()
    total_created = 0
    total_skipped = 0

    for city_data in cities:
        city_name = city_data["city"]
        lat = city_data["lat"]
        lon = city_data["lon"]
        logger.info("شهر: %s (%.4f, %.4f)", city_name, lat, lon)

        for subcategory in SUBCATEGORIES:
            place_type = SUBCATEGORY_TO_PLACE_TYPE[subcategory]

            count_resp = safe_request(
                "GET",
                f"{BASE_URL}/count/",
                headers=HEADERS,
                params={
                    "$filter": (
                        f"lat eq {lat} and lon eq {lon} "
                        f"and subcategory eq {subcategory} "
                        f"and buffer eq {BUFFER_METERS}"
                    )
                },
            )
            if not count_resp:
                logger.error("Count failed | %s | %s", city_name, subcategory)
                continue

            count_data = count_resp.json()
            total_count = (
                count_data.get("data", {}).get("count")
                or count_data.get("count")
                or count_data.get("odata.count", 0)
            )
            logger.info("  %s: تعداد %s", subcategory, total_count)
            if total_count == 0:
                continue

            pages = math.ceil(total_count / TOP_PER_PAGE)

            for page in range(pages):
                skip = page * TOP_PER_PAGE
                resp = safe_request(
                    "GET",
                    f"{BASE_URL}/list/",
                    headers=HEADERS,
                    params={
                        "$skip": skip,
                        "$top": TOP_PER_PAGE,
                        "$filter": (
                            f"lat eq {lat} and lon eq {lon} "
                            f"and subcategory eq {subcategory} "
                            f"and buffer eq {BUFFER_METERS} "
                            f"and sort eq true"
                        ),
                    },
                )
                if not resp:
                    logger.warning("Page skipped | %s | %s | page %s", city_name, subcategory, page + 1)
                    continue

                items = resp.json().get("value", [])
                for item in items:
                    coords = item.get("location", {}).get("coordinates", [None, None])
                    lon_item, lat_item = coords[0], coords[1]
                    if lat_item is None or lon_item is None:
                        total_skipped += 1
                        continue
                    name_fa = (item.get("name") or "").strip()
                    address = (item.get("address") or "").strip()
                    city_item = item.get("city") or city_name
                    try:
                        place, created = ensure_place_and_translation(
                            place_type=place_type,
                            city=city_item,
                            address=address,
                            latitude=lat_item,
                            longitude=lon_item,
                            name_fa=name_fa or "بدون نام",
                            name_en=item.get("name_en"),
                        )
                        if created:
                            total_created += 1
                            create_detail_tables(place, subcategory, item)
                        else:
                            total_skipped += 1
                    except Exception as e:
                        logger.exception("خطا در ذخیره مکان: %s", e)
                        total_skipped += 1

                time.sleep(SLEEP_BETWEEN_PAGES)

    logger.info("پایان. ایجاد شده: %s | رد شده/تکراری: %s", total_created, total_skipped)

    # همگام‌سازی با پوشه temp_data (داده‌های واردشده به DB در CSV هم ذخیره شوند)
    try:
        from team13.get_data.export_to_temp_data import export_team13_to_temp_data
        out_dir = export_team13_to_temp_data()
        logger.info("خروجی CSV در: %s", out_dir)
    except Exception as e:
        logger.exception("خطا در export به temp_data: %s", e)


if __name__ == "__main__":
    main()
