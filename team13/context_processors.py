# Context processor برای قرار دادن وضعیت کاربر (Core) در قالب‌های team13

from .core_auth import get_current_user_info


def team13_user_context(request):
    """
    فقط برای درخواست‌های زیرمسیر /team13/ متغیر team13_user را به context اضافه می‌کند
    تا در هدر صفحات (ورود/خروج، نام کاربر) استفاده شود.
    """
    if not request.path.startswith("/team13/"):
        return {}
    user_info = get_current_user_info(request)
    return {"team13_user": user_info}
