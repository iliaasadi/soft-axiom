# فراخوانی API تخمین زمان رسیدن (ETA) مپ — مرحله ۴ فاز ۷
# مستندات: https://support.map.ir/developers/api/eta/1-0-0/documents/
# پارامترها: x-api-key (Header)، coordinates در path به صورت:
#   origin_longitude,origin_latitude;destination_longitude,destination_latitude

import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

# آدرس پایهٔ ETA مپ (مسیریابی با خودرو)
MAPIR_ETA_BASE = "https://map.ir"
MAPIR_ETA_PATH = "eta/route/v1/driving"
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


def fetch_route_eta(lon_origin, lat_origin, lon_dest, lat_dest):
    """
    فراخوانی API ETA مپ برای مسیر بین دو نقطه (حالت رانندگی).

    ورودی: طول و عرض مبدأ، طول و عرض مقصد.
    خروجی: (distance_km, duration_seconds) در صورت موفقیت؛ در غیر این صورت (None, None).
    """
    api_key = get_mapir_api_key()
    if not api_key:
        return None, None

    # ساختار مختصات طبق مستندات: origin_longitude,origin_latitude;destination_longitude,destination_latitude
    coordinates = f"{lon_origin},{lat_origin};{lon_dest},{lat_dest}"
    # برای قرار گرفتن در path ممکن است نیاز به encode باشد
    coordinates_encoded = quote(coordinates, safe=",")
    url = f"{MAPIR_ETA_BASE}/{MAPIR_ETA_PATH}/{coordinates_encoded}"

    try:
        import requests
        resp = requests.get(
            url,
            headers={"x-api-key": api_key},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.debug("Map.ir ETA HTTP %s: %s", resp.status_code, url)
            return None, None
        data = resp.json()
        routes = data.get("routes") or data.get("route")
        if not routes:
            # گاهی خروجی به صورت مستقیم route است
            if "distance" in data and "duration" in data:
                dist = data.get("distance")
                dur = data.get("duration")
                if dist is not None and dur is not None:
                    return _normalize_distance(dist), _normalize_duration(dur)
            return None, None
        # routes می‌تواند آرایه یا یک آبجکت باشد
        if isinstance(routes, list):
            route = routes[0] if routes else {}
        else:
            route = routes
        distance = route.get("distance")
        duration = route.get("duration")
        if distance is None and duration is None:
            return None, None
        return _normalize_distance(distance), _normalize_duration(duration)
    except Exception as e:
        logger.debug("Map.ir ETA request failed: %s", e)
        return None, None


def _normalize_distance(v):
    """تبدیل فاصله به کیلومتر (اگر متر باشد)."""
    if v is None:
        return None
    try:
        v = float(v)
        if v > 1000:
            return round(v / 1000.0, 2)
        return round(v, 2)
    except (TypeError, ValueError):
        return None


def _normalize_duration(v):
    """تبدیل مدت به ثانیه (اگر میلی‌ثانیه یا دقیقه باشد)."""
    if v is None:
        return None
    try:
        v = float(v)
        if v < 100:
            return int(round(v * 60))
        if v > 10000:
            return int(round(v / 1000.0))
        return int(round(v))
    except (TypeError, ValueError):
        return None
