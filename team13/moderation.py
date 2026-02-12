# منطق تأیید پیشنهاد مکان (Internal Moderation)

from django.db import transaction

from .models import Image, Place, PlaceContribution, PlaceTranslation

TEAM13_DB = "team13"


def approve_contribution(contribution_id):
    """
    تأیید یک PlaceContribution: ایجاد Place در دیتابیس team13، انتقال تصاویر به Image با target_type=place، حذف پیشنهاد.

    Args:
        contribution_id: UUID (یا str) شناسه PlaceContribution.

    Returns:
        Place: مکان ایجاد شده.

    Raises:
        PlaceContribution.DoesNotExist: اگر پیشنهاد یافت نشود.
    """
    contribution = PlaceContribution.objects.using(TEAM13_DB).get(contribution_id=contribution_id)
    with transaction.atomic(using=TEAM13_DB):
        place = Place.objects.using(TEAM13_DB).create(
            type=contribution.type,
            city=contribution.city or "",
            address=contribution.address or "",
            latitude=contribution.latitude,
            longitude=contribution.longitude,
        )
        PlaceTranslation.objects.using(TEAM13_DB).create(
            place=place,
            lang="fa",
            name=contribution.name_fa,
            description="",
        )
        if contribution.name_en:
            PlaceTranslation.objects.using(TEAM13_DB).create(
                place=place,
                lang="en",
                name=contribution.name_en,
                description="",
            )
        Image.objects.using(TEAM13_DB).filter(
            target_type=Image.TargetType.PENDING_PLACE,
            target_id=contribution.contribution_id,
        ).update(target_type=Image.TargetType.PLACE, target_id=place.place_id)
        contribution.delete()
    return place
