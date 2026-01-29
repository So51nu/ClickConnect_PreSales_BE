# salelead/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SalesLead, SalesLeadUpdate, SiteVisit, SiteVisitRescheduleHistory
from common.tasks import (
    send_salesleadupdate_email,
    send_new_lead_to_cp,
    send_sitevisit_created_email,
    send_sitevisit_reschedule_email,
)


@receiver(post_save, sender=SalesLeadUpdate)
def salesleadupdate_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    # immediate async email to created_by
    if instance.created_by and instance.created_by.email:
        send_salesleadupdate_email.delay(instance.pk)


@receiver(post_save, sender=SiteVisit)
def sitevisit_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    send_sitevisit_created_email.delay(instance.pk)


@receiver(post_save, sender=SiteVisitRescheduleHistory)
def sitevisit_reschedule_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    send_sitevisit_reschedule_email.delay(instance.pk)


@receiver(post_save, sender=SalesLead)
def saleslead_post_save(sender, instance, created, **kwargs):
    if not created:
        return
    # notify CP on new lead
    if getattr(instance, "channel_partner", None):
        send_new_lead_to_cp.delay(instance.pk)
