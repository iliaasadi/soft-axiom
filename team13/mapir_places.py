# API مکان‌های Map.ir (Places) — مطابق Postman Collection
# Endpoints: air-nearest, route-nearest, count, list
# احراز هویت: هدر x-api-key با مقدار MAPIR_API_KEY یا API_KEY

import logging

logger = logging.getLogger(__name__)

MAPIR_PLACES_BASE = "https://map.ir/places"
REQUEST_TIMEOUT = 10


def get_mapir_api_key():
    """کلید API مپ را از تنظیمات یا متغیر محیطی برمی‌گرداند."""
    try:
        from django.conf import settings
        key = getattr(settings, "MAPIR_API_KEY", None) or ""
        if key:
            return key.strip()
    except Exception:
        pass
    import os
    return (os.environ.get("MAPIR_API_KEY") or os.environ.get("API_KEY") or "").strip()


def _request(endpoint, params):
    """درخواست GET به Map.ir Places با پارامتر $filter و غیره."""
    api_key = get_mapir_api_key()
    if not api_key:
        return None
    url = f"{MAPIR_PLACES_BASE}/{endpoint}"
    try:
        import requests
        resp = requests.get(
            url,
            headers={"x-api-key": api_key},
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.debug("Map.ir Places %s HTTP %s", endpoint, resp.status_code)
            return None
        return resp.json()
    except Exception as e:
        logger.debug("Map.ir Places %s failed: %s", endpoint, e)
        return None


def places_air_nearest(lat, lon, subcategory):
    """
    نزدیک‌ترین مکان از یک دسته — فاصلهٔ هوایی.
    subcategory مثال: school, hospital, hotel
    خروجی: دادهٔ مکان (data) یا None
    """
    params = {
        "$filter": f"lat eq {lat} and lon eq {lon} and subcategory eq {subcategory}",
    }
    data = _request("air-nearest", params)
    if data is None:
        return None
    return data.get("data")


def places_route_nearest(lat, lon, subcategory):
    """
    نزدیک‌ترین مکان از یک دسته — فاصلهٔ مسیر.
    خروجی: دادهٔ مکان شامل distance.amount (متر) یا None
    """
    params = {
        "$filter": f"lat eq {lat} and lon eq {lon} and subcategory eq {subcategory}",
    }
    data = _request("route-nearest", params)
    if data is None:
        return None
    return data.get("data")


def places_count(lat, lon, subcategory, buffer_meters=15000):
    """
    تعداد مکان‌های یک دسته در شعاع buffer (حداکثر ۱۵۰۰۰ متر).
    خروجی: عدد یا None
    """
    params = {
        "$filter": (
            f"lat eq {lat} and lon eq {lon} "
            f"and subcategory eq {subcategory} "
            f"and buffer eq {buffer_meters}"
        ),
    }
    data = _request("count", params)
    if data is None:
        return None
    return (data.get("data") or {}).get("count")


def places_list(lat, lon, subcategory, buffer_meters=15000, skip=0, top=20):
    """
    لیست مکان‌های یک دسته در شعاع buffer، مرتب‌شده بر اساس فاصله.
    top حداکثر ۲۰.
    خروجی: لیست آیتم‌ها (هر آیتم: name, address, location.coordinates, distance و ...)
    """
    params = {
        "$skip": skip,
        "$top": min(20, max(1, top)),
        "$filter": (
            f"lat eq {lat} and lon eq {lon} "
            f"and subcategory eq {subcategory} "
            f"and buffer eq {buffer_meters} "
            f"and sort eq true"
        ),
    }
    data = _request("list", params)
    if data is None:
        return []
    return data.get("value") or []


def emergency_places_from_mapir(lat, lon, limit=20):
    """
    لیست نزدیک‌ترین مراکز امدادی (بیمارستان/درمانگاه) از Map.ir برای حالت اضطراری.
    خروجی: لیست دیکشنری با کلیدهای name_fa, address, latitude, longitude, distance_km, source=mapir
    """
    items = places_list(lat, lon, "hospital", buffer_meters=15000, skip=0, top=limit)
    if not items:
        # امتحان زیردستهٔ دیگر مراقبت سلامت
        items = places_list(lat, lon, "clinic", buffer_meters=15000, skip=0, top=limit)
    result = []
    for item in items:
        loc = item.get("location") or {}
        coords = loc.get("coordinates") or [None, None]
        lon_item, lat_item = coords[0], coords[1]
        if lat_item is None or lon_item is None:
            continue
        dist = item.get("distance") or {}
        amount = dist.get("amount")
        if amount is not None:
            dist_km = round(float(amount) / 1000.0, 2)
        else:
            # محاسبهٔ تقریبی اگر Map.ir فاصله نداد
            from math import radians, sin, cos, sqrt, atan2
            R = 6371
            lat1, lon1 = radians(lat), radians(lon)
            lat2, lon2 = radians(lat_item), radians(lon_item)
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            dist_km = round(2 * R * atan2(sqrt(a), sqrt(1 - a)), 2)
        result.append({
            "place_id": None,
            "name_fa": (item.get("name") or "").strip() or "مرکز امدادی",
            "address": (item.get("address") or "").strip(),
            "latitude": lat_item,
            "longitude": lon_item,
            "distance_km": dist_km,
            "eta_minutes": max(1, round(dist_km / 0.5)),
            "source": "mapir",
        })
    return result
