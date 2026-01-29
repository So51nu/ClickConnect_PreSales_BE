from django.contrib import admin
from .models import Booking,BookingApplicant,BookingAttachment,BookingKycRequest,BookingStatusHistory
# Register your models here.

admin.site.register([Booking,BookingApplicant,BookingAttachment,BookingKycRequest,BookingStatusHistory])
