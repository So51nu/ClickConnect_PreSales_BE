# booking/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Booking
from common.tasks import (
    send_booking_created_email,
    schedule_booking_slab_reminders,
)


@receiver(post_save, sender=Booking)
def booking_post_save(sender, instance, created, **kwargs):
    if created:
        send_booking_created_email.delay(instance.pk)

        # only for custom payment plans
        if instance.payment_plan_type == "CUSTOM" and instance.custom_payment_plan:
            schedule_booking_slab_reminders.delay(instance.pk)
