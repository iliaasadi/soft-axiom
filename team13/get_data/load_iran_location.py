"""
بارگذاری داده‌های پوشه iran_location (provinces, cities, villages) به دیتابیس team13.

مطابق فاز ۵ جدول جداگانهٔ استان/شهر/روستا نداریم؛ فقط Place و PlaceTranslation.
بنابراین هر استان، شهر و (اختیاری) روستا به صورت یک Place با type=entertainment
ذخیره می‌شود تا در مسیریابی و نمایش مکان استفاده شود.

فایل‌های ورودی:
  - provinces.json
  - cities.json
  - villages.json (اختیاری با --with-villages)
  - iran_locations_complete.json (اگر بخواهیم یک فایل واحد استفاده کنیم؛ فعلاً از سه فایل جدا استفاده می‌کنیم)

اجرا از ریشهٔ پروژه:
  py -3.11 team13/get_data/load_iran_location.py
  py -3.11 team13/get_data/load_iran_location.py --with-villages
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path

# اضافه کردن ریشهٔ پروژه به path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

if os.environ.get("DJANGO_SETTINGS_MODULE") is None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app404.settings")
import django
django.setup()

from team13.models import Place, PlaceTranslation

# نام فضای UUID ثابت برای شناسه‌های یکتا و قابل تکرار از iran_location
NAMESPACE_IRAN_LOCATION = uuid.uuid5(uuid.NAMESPACE_URL, "https://team13.axiom/iran_location")
IRAN_LOCATION_DIR = _script_dir / "iran_location"
DB = "team13"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("load_iran_location")


def ensure_place_entertainment(place_id, city, address, latitude, longitude, name_fa, name_en=None):
    """یک Place با type=entertainment و ترجمهٔ fa (و در صورت وجود en) ایجاد یا به‌روزرسانی می‌کند."""
    place, created = Place.objects.using(DB).get_or_create(
        place_id=place_id,
        defaults={
            "type": Place.PlaceType.ENTERTAINMENT,
            "city": city or "",
            "address": address or "",
            "latitude": float(latitude),
            "longitude": float(longitude),
        },
    )
    if not created:
        place.city = city or ""
        place.address = address or ""
        place.latitude = float(latitude)
        place.longitude = float(longitude)
        place.save(update_fields=["city", "address", "latitude", "longitude"], using=DB)

    PlaceTranslation.objects.using(DB).update_or_create(
        place=place,
        lang="fa",
        defaults={"name": name_fa or "بدون نام", "description": ""},
    )
    if name_en:
        PlaceTranslation.objects.using(DB).update_or_create(
            place=place,
            lang="en",
            defaults={"name": name_en, "description": ""},
        )
    return place, created


def load_provinces():
    """بارگذاری استان‌ها از provinces.json به عنوان Place (مرکز استان)."""
    path = IRAN_LOCATION_DIR / "provinces.json"
    if not path.exists():
        logger.warning("فایل یافت نشد: %s", path)
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    count = 0
    for p in data:
        pid = p.get("province_id")
        name_fa = p.get("name_fa") or ""
        name_en = p.get("name_en") or ""
        loc = p.get("location") or {}
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None or not name_fa:
            continue
        place_id = uuid.uuid5(NAMESPACE_IRAN_LOCATION, f"province_{pid}")
        ensure_place_entertainment(
            place_id=place_id,
            city="",
            address=name_fa,
            latitude=lat,
            longitude=lon,
            name_fa=f"مرکز استان {name_fa}",
            name_en=f"Province center: {name_en}" if name_en else None,
        )
        count += 1
    logger.info("استان‌ها: %s رکورد", count)
    return count


def load_cities():
    """بارگذاری شهرها از cities.json به عنوان Place (مرکز شهر)."""
    path = IRAN_LOCATION_DIR / "cities.json"
    if not path.exists():
        logger.warning("فایل یافت نشد: %s", path)
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    count = 0
    for c in data:
        cid = c.get("city_id")
        name_fa = c.get("name_fa") or ""
        name_en = c.get("name_en") or ""
        prov = c.get("province") or {}
        prov_fa = prov.get("name_fa") or ""
        loc = c.get("location") or {}
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None or not name_fa:
            continue
        place_id = uuid.uuid5(NAMESPACE_IRAN_LOCATION, f"city_{cid}")
        ensure_place_entertainment(
            place_id=place_id,
            city=name_fa,
            address=prov_fa,
            latitude=lat,
            longitude=lon,
            name_fa=f"مرکز شهر {name_fa}",
            name_en=f"City: {name_en}" if name_en else None,
        )
        count += 1
    logger.info("شهرها: %s رکورد", count)
    return count


def load_villages():
    """بارگذاری روستاها از villages.json به عنوان Place (روستا)."""
    path = IRAN_LOCATION_DIR / "villages.json"
    if not path.exists():
        logger.warning("فایل یافت نشد: %s", path)
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    count = 0
    for v in data:
        vid = v.get("village_id")
        name_fa = v.get("name_fa") or ""
        name_en = v.get("name_en") or name_fa
        city = v.get("city") or {}
        city_fa = city.get("name_fa") or ""
        loc = v.get("location") or {}
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None or not name_fa:
            continue
        place_id = uuid.uuid5(NAMESPACE_IRAN_LOCATION, f"village_{vid}")
        ensure_place_entertainment(
            place_id=place_id,
            city=city_fa,
            address=name_fa,
            latitude=lat,
            longitude=lon,
            name_fa=f"روستای {name_fa}",
            name_en=f"Village: {name_en}" if name_en else None,
        )
        count += 1
    logger.info("روستاها: %s رکورد", count)
    return count


def main():
    import argparse
    parser = argparse.ArgumentParser(description="بارگذاری iran_location در دیتابیس team13")
    parser.add_argument("--with-villages", action="store_true", help="روستاها را هم بارگذاری کن (تعداد زیاد)")
    args = parser.parse_args()

    total = 0
    total += load_provinces()
    total += load_cities()
    if args.with_villages:
        total += load_villages()

    # همگام‌سازی با temp_data
    try:
        from team13.get_data.export_to_temp_data import export_team13_to_temp_data
        out_dir = export_team13_to_temp_data()
        logger.info("خروجی CSV در: %s", out_dir)
    except Exception as e:
        logger.exception("خطا در export به temp_data: %s", e)

    logger.info("پایان. مجموع رکوردهای بارگذاری‌شده از iran_location: %s", total)


if __name__ == "__main__":
    main()
