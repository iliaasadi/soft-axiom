from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    JWT_ACCESS_TTL_SECONDS=(int, 15 * 60),
    JWT_REFRESH_TTL_SECONDS=(int, 7 * 24 * 60 * 60),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-change-me")
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

TEAM_APPS = [s.strip() for s in env("TEAM_APPS", default="team1,team2,team3,team4,team5,team6,team7,team8,team9,team10,team11,team12,team13").split(",") if s.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # 3rd-party
    "corsheaders",

    # Local
    "core",
    *TEAM_APPS,
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "core.middleware.JWTAuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "app404.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "team13.context_processors.team13_user_context",
            ],
        },
    }
]

WSGI_APPLICATION = "app404.wsgi.application"

# مطابق فاز ۵ (P5_Axiom): همهٔ دیتابیس‌ها SQLite — کاربران، مکان‌ها، رویدادها، تصاویر، نظرات و غیره در SQLite ذخیره می‌شوند.
# از env فقط در صورت تمایل به تغییر مسیر فایل SQLite استفاده می‌شود؛ در غیر این صورت مسیر پیش‌فرض اعمال می‌شود.
def _sqlite_db_path(relative_path):
    path = BASE_DIR / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=_sqlite_db_path("db.sqlite3"),
    ),
}
# اطمینان از اینکه default حتماً SQLite باشد (اگر در .env به اشتباه mysql/postgres آمده باشد، نادیده گرفته می‌شود)
if "sqlite" not in DATABASES["default"]["ENGINE"]:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }

for t in TEAM_APPS:
    key = f"{t.upper()}_DATABASE_URL"
    default_url = _sqlite_db_path(f"{t}/{t}.sqlite3")
    db_config = env.db(key, default=default_url)
    if "sqlite" not in db_config.get("ENGINE", ""):
        team_db_dir = BASE_DIR / t
        team_db_dir.mkdir(parents=True, exist_ok=True)
        db_config = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": team_db_dir / f"{t}.sqlite3",
        }
    DATABASES[t] = db_config

DATABASE_ROUTERS = ["core.db_router.TeamPerAppRouter"]


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "http")

AUTH_USER_MODEL = "core.User"

JWT_SECRET = env("JWT_SECRET", default=SECRET_KEY)
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TTL_SECONDS = env("JWT_ACCESS_TTL_SECONDS")
JWT_REFRESH_TTL_SECONDS = env("JWT_REFRESH_TTL_SECONDS")

JWT_COOKIE_SECURE = env.bool("JWT_COOKIE_SECURE", default=False)
JWT_COOKIE_SAMESITE = env("JWT_COOKIE_SAMESITE", default="Lax")

# آدرس سامانه مرکزی (Core) برای احراز هویت — در صورت خالی بودن از request.user همین سرور استفاده می‌شود.
# برای اجرای محلی: CORE_BASE_URL=http://localhost:8000 یا خالی
CORE_BASE_URL = env("CORE_BASE_URL", default="").strip()

# صفحه ورود برای ریدایرکت در صورت نیاز به احراز هویت (مثلاً امتیازدهی در team13)
LOGIN_URL = "/auth/"

# کلیدهای API نشان (neshan.ir) — مسیریابی، جستجو، نقشه
# service: فراخوانی از بک‌اند (مسیر، reverse، جستجو). web: برای استفاده در فرانت/نقشه در صورت نیاز.
NESHAN_API_KEY_SERVICE = env("NESHAN_API_KEY_SERVICE", default="").strip()
NESHAN_API_KEY_WEB = env("NESHAN_API_KEY_WEB", default="").strip()
# fallback برای سازگاری با یک کلید واحد
NESHAN_API_KEY = env("NESHAN_API_KEY", default="").strip() or NESHAN_API_KEY_SERVICE or env("API_KEY", default="").strip()

CORS_ALLOW_CREDENTIALS = True

if DEBUG:
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^http://localhost:\d+$",
        r"^http://127\.0\.0\.1:\d+$",
    ]
else:
    CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])


CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
