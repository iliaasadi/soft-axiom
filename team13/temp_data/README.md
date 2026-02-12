# داده‌های نمونه دیتابیس — سرویس Facilities & Transportation

این پوشه شامل فایل‌های CSV نمونه برای **هر جدول** دیتابیس است (مطابق فاز ۵ و طراحی P5_Axiom). دیتابیس با **SQLite** (فاز ۷) استفاده می‌شود.

## ساختار جداول و فایل‌ها

| فایل CSV | جدول دیتابیس | تعداد سطر نمونه | توضیح کوتاه |
|----------|---------------|-----------------|--------------|
| `places.csv` | `team13_places` | ۱۵ | مکان‌ها (POI): ۵ هتل، ۵ رستوران، ۵ موزه — شناسه UUID، نوع، شهر، آدرس، عرض/طول جغرافیایی |
| `place_translations.csv` | `team13_place_translations` | ۵ | ترجمه نام و توضیح مکان (فارسی/انگلیسی) |
| `events.csv` | `team13_events` | ۵ | رویدادها: تاریخ و زمان شروع/پایان، شهر، آدرس، مختصات |
| `event_translations.csv` | `team13_event_translations` | ۵ | ترجمه عنوان و توضیح رویداد (fa/en) |
| `images.csv` | `team13_images` | ۵ | تصاویر مرتبط با مکان یا رویداد — target_type، target_id، image_url |
| `comments.csv` | `team13_comments` | ۵ | نظرات/امتیاز (۱–۵) برای مکان یا رویداد |
| `hotel_details.csv` | `team13_hotel_details` | ۵ | جزئیات هتل: ستاره (۱–۵)، حداکثر قیمت (تومان) |
| `restaurant_details.csv` | `team13_restaurant_details` | ۵ | جزئیات رستوران: نوع غذا (cuisine)، قیمت متوسط هر وعده |
| `museum_details.csv` | `team13_museum_details` | ۵ | جزئیات موزه: ساعت باز/بسته، قیمت بلیط |
| `place_amenities.csv` | `team13_place_amenities` | ۵ | امکانات مکان (پارکینگ، استخر، وای‌فای و …) |
| `route_logs.csv` | `team13_route_logs` | ۵ | ثبت سفر کاربر: مبدأ، مقصد، نوع حمل‌ونقل (car/walk/transit) |

## روابط کلیدی

- **places** ← place_translations، place_amenities، hotel_details، restaurant_details، museum_details، route_logs (source/destination)
- **events** ← event_translations
- **images** و **comments**: target_type + target_id به مکان یا رویداد اشاره می‌کنند (polymorphic)
- **user_id** در route_logs به کاربر سامانه مرکزی (Core) اشاره دارد؛ در این جدول فقط شناسه ذخیره می‌شود.

## نصب داده نمونه در دیتابیس

از ریشه پروژه (پس از اجرای `migrate`):

```bash
py -3.11 manage.py loaddata_team13_csv
```

برای خالی کردن قبلی و بارگذاری مجدد:

```bash
py -3.11 manage.py loaddata_team13_csv --clear
```

اگر جداول team13 در دیتابیس وجود نداشتند، یک‌بار اجرا کنید:

```bash
py -3.11 manage.py migrate --database=team13 --run-syncdb
```

## فرمت CSV

- جداکننده: کاما (`,`)
- هدر اول هر فایل نام ستون‌هاست.
- شناسه‌ها به صورت UUID هستند؛ در route_logs فیلد `id` عددی است.
- تاریخ/زمان به صورت `YYYY-MM-DD HH:MM:SS`.
- اعداد اعشاری با نقطه (مثل `35.6892`).
