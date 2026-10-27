from django.conf import settings


def site_settings(request):
    return {"currency": settings.CURRENCY_SYMBOL, "site_name": settings.SITE_NAME}
