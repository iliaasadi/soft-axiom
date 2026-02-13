# دادهٔ نمونه برای بارگذاری در دیتابیس team13

فایل‌های CSV این پوشه با اسکریپت `load_temp_data.py` یا دستور `loaddata_team13_csv` در دیتابیس SQLite تیم ۱۳ بارگذاری می‌شوند.

## فایل‌ها و ستون‌ها

| فایل | ستون‌های اصلی |
|------|----------------|
| places.csv | place_id, type, city, address, latitude, longitude |
| place_translations.csv | place_id, lang, name, description |
| events.csv | event_id, start_at, end_at, city, address, latitude, longitude |
| event_translations.csv | event_id, lang, title, description |
| images.csv | image_id, target_type, target_id, image_url |
| comments.csv | comment_id, target_type, target_id, rating, created_at |
| hotel_details.csv | place_id, stars, price_range |
| restaurant_details.csv | place_id, cuisine, avg_price |
| museum_details.csv | place_id, open_at, close_at, ticket_price |
| place_amenities.csv | place_id, amenity_name |
| route_logs.csv | source_place_id, destination_place_id, travel_mode, user_id, created_at |

- نوع مکان (type): `hotel`, `food`, `hospital`, `museum`, `entertainment`
- زبان (lang): `fa`, `en`
- همهٔ فایل‌ها با هدر و encoding UTF-8.
