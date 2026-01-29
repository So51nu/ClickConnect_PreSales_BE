# costsheet/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CostSheet
from common.tasks import send_costsheet_email


@receiver(post_save, sender=CostSheet)
def costsheet_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    send_costsheet_email.delay(instance.pk)
