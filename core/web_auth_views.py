from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme

from core.jwt_utils import create_access_token, create_refresh_token
from core.views import _set_auth_cookies  # reuse same cookie logic

User = get_user_model()


def _get_safe_next(request):
    """آدرس next برای ریدایرکت پس از ورود (فقط اگر مجاز باشد)."""
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=request.get_host(), require_https=request.is_secure()):
        return next_url
    return None


@require_http_methods(["GET", "POST"])
def login_page(request):
    error = None

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""

        user = authenticate(request, username=email, password=password)
        if user is None:
            error = "ایمیل یا رمز عبور اشتباه است."
        elif not user.is_active:
            error = "حساب کاربری غیرفعال است."
        else:
            access = create_access_token(user)
            refresh = create_refresh_token(user)
            next_url = _get_safe_next(request)
            resp = redirect(next_url if next_url else "home")
            _set_auth_cookies(resp, access, refresh, settings)
            return resp

    return render(request, "auth/login.html", {"error": error, "next": request.GET.get("next", "")})


@require_http_methods(["GET", "POST"])
def signup_page(request):
    error = None

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        password = request.POST.get("password") or ""
        first_name = request.POST.get("first_name") or ""
        last_name = request.POST.get("last_name") or ""
        age_raw = (request.POST.get("age") or "").strip()

        age = None
        if age_raw:
            try:
                age = int(age_raw)
            except ValueError:
                error = "سن باید عدد باشد."

        if not error:
            if not email or not password:
                error = "ایمیل و رمز عبور الزامی است."
            elif User.objects.filter(email=email).exists():
                error = "این ایمیل قبلاً ثبت شده است."
            else:
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    age=age,
                )
                access = create_access_token(user)
                refresh = create_refresh_token(user)
                resp = redirect("home")
                _set_auth_cookies(resp, access, refresh, settings)
                return resp

    return render(request, "auth/signup.html", {"error": error})


@require_http_methods(["GET", "POST"])
def logout_page(request):
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        request.user.token_version += 1
        request.user.save(update_fields=["token_version"])

    resp = redirect("home")
    resp.delete_cookie("access_token", path="/")
    resp.delete_cookie("refresh_token", path="/api/auth/")
    return resp
