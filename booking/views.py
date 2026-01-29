# booking/views.py
from rest_framework import serializers
import logging
import re
from django.db.models import F
from django.core.mail import send_mail
from django.conf import settings
from django.db import transaction   
from .models import Booking, BookingAttachment, BookingStatus 
from rest_framework import status, permissions, viewsets
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.decorators import action
from clientsetup.models import InventoryStatusHistory
from .models import Booking
from .serializers import BookingSerializer
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from clientsetup.models import UnitStatus
from .models import *
from django.utils import timezone
from django.core.files.base import ContentFile
from clientsetup.models import AvailabilityStatus
from common.pdf_utils import render_html_to_pdf_bytes
from .models import Booking, BookingAttachment
from .serializers import BookingSerializer
log = logging.getLogger(__name__)
from django.db import transaction


# bookings/views.py
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status, permissions

from salelead.models import PaymentLead
from salelead.serializers import KycPaymentLeadCreateSerializer, PaymentLeadSerializer
from accounts.permissions import IsKycUser  #
from rest_framework.decorators import action
from rest_framework import permissions, status
from rest_framework.response import Response

from salelead.models import PaymentLead
from salelead.serializers import PaymentLeadSerializer, KycPaymentLeadCreateSerializer
from accounts.permissions import IsKycUser
from salelead.views import _project_ids_for_user  # jaha ye function hai


class BookingViewSet(viewsets.ModelViewSet):
    """
    /api/client/bookings/
      GET    -> list
      POST   -> 1-shot create (booking + applicants + attachments)
    /api/client/bookings/{id}/
      GET    -> detail
      PATCH  -> update (e.g. status / kyc_status)
      DELETE -> cancel (optional)

    /api/client/bookings/my-bookings/
      GET    -> list of bookings created by request.user
    """

    queryset = (
        Booking.objects
        .select_related("project", "tower", "floor", "unit","unit__inventory_items" ,"sales_lead", "channel_partner","project__belongs_to","created_by")
        .prefetch_related("applicants", "attachments")
        .all()
    )
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # -------------------------------------------------
    # FILTERS FOR LIST ENDPOINT
    # -------------------------------------------------
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_superuser or user.is_staff:
            return qs

        role = getattr(user, "role", None)
        role_code = role.upper() if isinstance(role, str) else getattr(role, "code", None)

        if role_code == "ADMIN":
            admin_id = user.id
        else:
            admin_id = getattr(user, "admin_id", None)

        if admin_id:
            qs = qs.filter(project__belongs_to_id=admin_id)

        # ---- filters ----
        q = self.request.query_params
        if q.get("project_id"):
            qs = qs.filter(project_id=q["project_id"])
        if q.get("unit_id"):
            qs = qs.filter(unit_id=q["unit_id"])
        if q.get("status"):
            qs = qs.filter(status=q["status"])

        return qs



    # -------------------------------------------------
    # CREATE: parse FormData bracket notation -> nested
    def create(self, request, *args, **kwargs):
        """
        Accept FE FormData with keys like:
          unit_id=2
          ...
          applicants[0][full_name]=...
          applicants[0][pan_front]=<file>
          attachments[0][label]=...
          attachments[0][file]=<file>

        and convert to:
          {
            ...,
            "applicants": [{...}, {...}],
            "attachments": [{...}, {...}]
          }

        so that BookingSerializer (nested) can handle it.
        """
        log.debug("📥 [BOOKING CREATE] raw data keys: %s", list(request.data.keys()))
        log.debug("📥 [BOOKING CREATE] raw files keys: %s", list(request.FILES.keys()))

        # Serializer ke known fields nikaal lo – extra fields (discount_percent,
        # photo, etc.) ko ignore kar denge taaki error na aaye.
        serializer_class = self.get_serializer_class()
        tmp_serializer = serializer_class()
        allowed_fields = set(tmp_serializer.fields.keys())

        group_pattern = re.compile(
            r"^(applicants|attachments|additional_charges)\[(\d+)\]\[(\w+)\]$"
        )

        base = {}
        applicants_map = {}
        attachments_map = {}
        additional_charges_map = {}

        # ---------- 1) Text + file values merged in request.data ----------
        for key, value in request.data.items():
            m = group_pattern.match(key)
            if m:
                group, idx_str, field = m.groups()
                idx = int(idx_str)

                if group == "applicants":
                    applicants_map.setdefault(idx, {})[field] = value
                else:  # attachments
                    attachments_map.setdefault(idx, {})[field] = value
            else:
                # Sirf woh fields pass karo jo BookingSerializer jaanta hai
                if key in allowed_fields:
                    base[key] = value
                else:
                    # discount_percent, final_amount, photo, etc. yahan log ho jayega
                    log.debug("Ignoring extra FE field %s=%r", key, value)

        # ---------- 2) Files ko bhi ensure karo (pan_front, file, etc.) ----------
        for key, file_obj in request.FILES.items():
            m = group_pattern.match(key)
            if m:
                group, idx_str, field = m.groups()
                idx = int(idx_str)

                if group == "applicants":
                    applicants_map.setdefault(idx, {})[field] = value
                elif group == "attachments":
                    attachments_map.setdefault(idx, {})[field] = value
                else:  # additional_charges
                    additional_charges_map.setdefault(idx, {})[field] = value

            else:
                if key in allowed_fields:
                    base[key] = file_obj
                else:
                    log.debug(
                        "Ignoring extra FE file field %s (name=%s)",
                        key,
                        getattr(file_obj, "name", None),
                    )

        # ---------- 3) Maps -> ordered lists (0,1,2...) ----------
        def _non_empty(d: dict) -> bool:
            # completely khaali rows ko skip karne ke liye (pure "" / None)
            return any(v not in ("", None) for v in d.values())

        applicants_list = [
            data
            for idx, data in sorted(applicants_map.items(), key=lambda t: t[0])
            if _non_empty(data)
        ]
        attachments_list = [
            data
            for idx, data in sorted(attachments_map.items(), key=lambda t: t[0])
            if _non_empty(data)
        ]

        additional_charges_list = [
            data
            for idx, data in sorted(additional_charges_map.items(), key=lambda t: t[0])
            if _non_empty(data)
        ]

        if applicants_list:
            base["applicants"] = applicants_list
        if attachments_list:
            base["attachments"] = attachments_list
        if additional_charges_list:
            base["additional_charges"] = additional_charges_list
        log.debug(
            "🧩 [BOOKING CREATE] parsed base (without nested): %s",
            {k: v for k, v in base.items() if k not in ("applicants", "attachments")},
        )
        log.debug(
            "🧩 [BOOKING CREATE] applicants=%d, attachments=%d",
            len(applicants_list),
            len(attachments_list),
        )

        raw_kyc_req_id = (
            request.data.get("kyc_request_id")
            or request.data.get("kyc_request")
        )

        # Agar serializer me 'kyc_request' naam ka field hai,
        # to usme id daal do (DRF PrimaryKeyRelatedField handle karega)
        if raw_kyc_req_id and "kyc_request" in allowed_fields and "kyc_request" not in base:
            base["kyc_request"] = raw_kyc_req_id

        # Ab default status set karo:
        # - agar KYC linked hai -> DRAFT
        # - agar KYC nahi hai -> BOOKED
        if "status" in allowed_fields and "status" not in base:
            if raw_kyc_req_id:
                # KYC wale case me pehle DRAFT rakhenge
                base["status"] = BookingStatus.DRAFT
            else:
                # KYC nahi hai to direct BOOKED
                base["status"] = BookingStatus.BOOKED

        # ---------- 4) DRF serializer validation + create ----------
        serializer = self.get_serializer(data=base, context={"request": request})

        if not serializer.is_valid():
            log.error("❌ Booking validation errors: %s", serializer.errors)
            log.error("❌ Parsed applicants: %s", applicants_list)
            log.error("❌ Parsed attachments: %s", attachments_list)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    

    def perform_create(self, serializer):
        """
        BookingSerializer.create() ko call karega,
        phir condition check karke project.belongs_to ko mail bhejega
        agar rate < approved limit.
        """
        request_user = self.request.user

        # outer transaction taaki on_commit kaam kare
        with transaction.atomic():
            booking = serializer.save()  # yahan serializer.create() chalta hai

            unit = booking.unit
            inv = getattr(unit, "inventory_items", None)

            customer_rate = getattr(booking, "customer_base_price_psf", None)
            inv_limit = getattr(inv, "approved_limit_price_psf", None) if inv else None

            should_alert = (
                inv is not None
                and customer_rate is not None
                and inv_limit is not None
                and customer_rate < inv_limit
            )

            if not should_alert:
                return

            project = booking.project
            admin_user = getattr(project, "belongs_to", None)
            if not (admin_user and admin_user.email):
                return

            subject = (
                f"Booking below approved limit price - "
                f"{booking.form_ref_no or booking.id}"
            )

            message_lines = [
                f"Dear {admin_user.get_full_name() or admin_user.username},",
                "",
                "A new booking has been created with rate below the approved limit.",
                "",
                f"Project: {project}",
                f"Unit: {booking.unit}",
                f"Customer Base Price (PSF): {customer_rate}",
                f"Approved Limit Price (PSF): {inv_limit}",
                f"Booking Ref: {booking.form_ref_no or booking.id}",
            ]

            if request_user and request_user.is_authenticated:
                message_lines.append(f"Created By: {request_user.get_full_name() or request_user.username}")

            message_lines.append("")
            message_lines.append("Please review this booking in the system.")

            message = "\n".join(message_lines)

            from_email = getattr(
                settings, "DEFAULT_FROM_EMAIL", "no-reply@presales.myciti.life"
            )

            # mail ko tabhi bhejo jab transaction safely commit ho jaye
            def _send_mail():
                send_mail(
                    subject,
                    message,
                    from_email,
                    [admin_user.email],
                    fail_silently=True,
                )

            transaction.on_commit(_send_mail)


    @action(
        detail=True,
        methods=["get", "post"],
        url_path="kyc-payment",
        permission_classes=[permissions.IsAuthenticated, IsKycUser],
    )
    def kyc_payment(self, request, pk=None):
        """
        GET  /api/book/bookings/<booking_id>/kyc-payment/
            -> all KYC payments for this booking (for_kyc=True), optional ?kyc_request_id=

        POST /api/book/bookings/<booking_id>/kyc-payment/
            Body:
            {
              "kyc_request_id": 7,
              "payment_type": "BOOKING",
              "payment_method": "ONLINE",
              "amount": 50000,
              ...
            }

            -> creates PaymentLead:
                - lead = booking.sales_lead
                - project = booking.project
                - booking = this
                - kyc_request = given
                - for_kyc = True
                - status default SUCCESS if not sent
        """
        user = request.user
        project_ids = _project_ids_for_user(user)

        booking = (
            self.get_queryset()
            .select_related("project", "sales_lead")
            .filter(project_id__in=project_ids)
            .get(pk=pk)
        )

        if request.method == "GET":
            qs = (
                PaymentLead.objects
                .filter(
                    booking=booking,
                    for_kyc=True,
                )
                .select_related("kyc_request", "created_by")
                .order_by("-payment_date", "-id")
            )

            # optional: filter by kyc_request_id
            kyc_req_id = request.query_params.get("kyc_request_id")
            if kyc_req_id:
                qs = qs.filter(kyc_request_id=kyc_req_id)

            serializer = PaymentLeadSerializer(qs, many=True, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        # POST - create
        serializer = KycPaymentLeadCreateSerializer(
            data=request.data,
            context={"request": request, "booking": booking},
        )
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()

        out = PaymentLeadSerializer(payment, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)


    @action(
        detail=True,
        methods=["post"],
        url_path="kyc-payment",
        permission_classes=[permissions.IsAuthenticated, IsKycUser],
    )
    def create_kyc_payment(self, request, pk=None):
        """
        Secret KYC payment API:
        - PaymentLead row create karega
        - lead + project booking se derive honge
        - for_kyc = True
        - status agar nahi diya to SUCCESS
        - sirf KYC role allowed
        """
        booking = self.get_object()

        serializer = KycPaymentLeadCreateSerializer(
            data=request.data,
            context={"request": request, "booking": booking},
        )
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()

        # response ke liye normal PaymentLead serializer use kar sakte ho
        out = PaymentLeadSerializer(payment, context={"request": request})
        return Response(out.data, status=status.HTTP_201_CREATED)



    @action(
        detail=True,
        methods=["post"],
        url_path="upload-signed-form",
        parser_classes=[MultiPartParser, FormParser],
    )
    def upload_signed_form(self, request, pk=None):
        """
        POST /api/book/bookings/<id>/upload-signed-form/

        Body: multipart/form-data
          - signed_booking_file: <PDF/image>

        Use-case:
        - Booking ho chuki hai
        - Print nikala, customer ne sign kiya
        - Scan karke yeh endpoint pe upload karoge
        """
        booking = self.get_object()

        file_obj = (
            request.FILES.get("signed_booking_file")
            or request.FILES.get("file")
        )

        if not file_obj:
            return Response(
                {"detail": "No file uploaded. Use 'signed_booking_file' in form-data."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        booking.signed_booking_file = file_obj
        booking.save(update_fields=["signed_booking_file"])

        serializer = self.get_serializer(booking)
        return Response(serializer.data, status=status.HTTP_200_OK)



    # -------------------------------------------------
    # MY BOOKINGS
    # -------------------------------------------------
    @action(detail=False, methods=["get"], url_path="my-bookings")
    def my_bookings(self, request):
        """
        Returns bookings created by the logged-in user.
        Ordered by latest booking on top.
        GET /api/client/bookings/my-bookings/
        """
        qs = (
            self.get_queryset()
            .filter(created_by=request.user)
            .order_by("-booking_date", "-created_at")  # newest first
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)



    @action(detail=False, methods=["get"], url_path="drafts-below-limit-price")
    def drafts_below_limit_price(self, request):
        """
        Sare DRAFT bookings:
        jaha Booking.customer_base_price_psf
        < Unit.Inventory.approved_limit_price_psf
        """
        qs = (
            self.get_queryset()
            .filter(
                status=BookingStatus.DRAFT,
                customer_base_price_psf__isnull=False,
                unit__inventory_items__approved_limit_price_psf__isnull=False,
                customer_base_price_psf__lt=F(
                    "unit__inventory_items__approved_limit_price_psf"
                ),
            )
            .order_by("-booking_date", "-created_at")
        )

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


    @action(detail=False, methods=["get"], url_path="by-sales-person")
    def by_sales_person(self, request):
        """
        GET /api/client/bookings/by-sales-person/
        
        Returns all bookings created by the salesperson,
        grouped by Inventory (project / tower / floor / unit).
        """
        user = request.user

        # Fetch bookings of this salesperson
        qs = (
            Booking.objects
            .filter(created_by=user)
            .select_related("project", "tower", "floor", "unit")
            .prefetch_related("applicants", "attachments")
            .order_by("unit_id")
        )

        grouped = {}

        for b in qs:
            inv_key = b.unit_id

            if inv_key not in grouped:
                grouped[inv_key] = {
                    "inventory": {
                        "project": b.project.name if b.project else None,
                        "tower": b.tower.name if b.tower else None,
                        "floor": b.floor.number if b.floor else None,
                        "unit_no": b.unit.unit_no if b.unit else None,
                        "unit_id": b.unit_id,
                    },
                    "bookings": []
                }

            grouped[inv_key]["bookings"].append({
                "id": b.id,
                "form_ref_no": b.form_ref_no,
                "primary_full_name": b.primary_full_name,
                "primary_mobile_number": b.primary_mobile_number,
                "primary_email": b.primary_email,
                "agreement_value": b.agreement_value,
                "agreement_value_words": b.agreement_value_words,
                "status": b.status,
                "created_at": b.created_at,
                "booking_date": b.booking_date,

                # nested applicants
                "applicants": [
                    {
                        "id": a.id,
                        "is_primary": a.is_primary,
                        "full_name": a.full_name,
                        "email": a.email,
                        "mobile_number": a.mobile_number,
                        "pan_no": a.pan_no,
                        "aadhar_no": a.aadhar_no,
                    }
                    for a in b.applicants.all()
                ],

                # nested attachments
                "attachments": [
                    {
                        "id": att.id,
                        "label": att.label,
                        "doc_type": att.doc_type,
                        "file": request.build_absolute_uri(att.file.url)
                            if att.file else None,

                        # 🧾 naya payment meta
                        "payment_mode": att.payment_mode,
                        "payment_ref_no": att.payment_ref_no,
                        "bank_name": att.bank_name,
                        "payment_amount": att.payment_amount,
                        "payment_date": att.payment_date,
                        "remarks": att.remarks,
                        "is_payment_proof": (att.doc_type == "PAYMENT_PROOF"),
                    }
                    for att in b.attachments.all()
                ],

            })

        return Response(list(grouped.values()))
    

    @action(detail=True, methods=["post"], url_path="generate-pdf")
    def generate_pdf(self, request, pk=None):
        """
        POST /api/book/bookings/<id>/generate-pdf/

        - Render booking PDF
        - Save as BookingAttachment (doc_type='BOOKING_FORM_PDF')
        - Return URL + status
        """
        booking = self.get_object()

        # context for template
        context = {
            "booking": booking,
            "applicants": booking.applicants.all(),
            "today": timezone.now().date(),
        }

        pdf_bytes = render_html_to_pdf_bytes(
            "booking/booking_form_pdf.html",
            context,
        )

        if not pdf_bytes:
            return Response(
                {"detail": "Failed to generate PDF."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        booking.attachments.filter(doc_type="BOOKING_FORM_PDF").delete()

        filename = f"booking_{booking.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.pdf"
        attachment = BookingAttachment(
            booking=booking,
            label="Booking Form PDF",
            doc_type="BOOKING_FORM_PDF",
        )
        attachment.file.save(filename, ContentFile(pdf_bytes), save=True)

        pdf_url = request.build_absolute_uri(attachment.file.url)

        return Response(
            {
                "id": booking.id,
                "form_ref_no": booking.form_ref_no,
                "status": booking.status,
                "status_label": booking.status_label,
                "pdf_url": pdf_url,
            },
            status=status.HTTP_200_OK,
        )
    

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm_booking(self, request, pk=None):
        booking = self.get_object()
        user = request.user

        project = booking.project
        belongs_to_id = project.belongs_to_id

        if not user.is_superuser:
            role = getattr(user, "role", None)
            role_code = role.upper() if isinstance(role, str) else getattr(role, "code", None)

            admin_id = user.id if role_code == "ADMIN" else getattr(user, "admin_id", None)

            if admin_id != belongs_to_id:
                return Response(
                    {"detail": "You are not allowed to confirm bookings for this project."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        if booking.status != BookingStatus.DRAFT:
            return Response(
                {"detail": "Only DRAFT bookings can be confirmed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # @action(detail=True, methods=["post"], url_path="confirm")
    # def confirm_booking(self, request, pk=None):
    #     booking = self.get_object()
    #     user = request.user

    #     # 🔐 project ownership check
    #     project = booking.project
    #     belongs_to_id = getattr(project, "belongs_to_id", None)
    #     if (
    #         belongs_to_id
    #         and belongs_to_id != user.id
    #         and not getattr(user, "is_superuser", False)
    #     ):
    #         return Response(
    #             {
    #                 "detail": "You are not allowed to confirm bookings for this project."
    #             },
    #             status=status.HTTP_403_FORBIDDEN,
    #         )

    #     # 👇 use plain string check, very explicit
    #     if str(booking.status) != "DRAFT":
    #         return Response(
    #             {"detail": "Only DRAFT bookings can be confirmed."},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

        # KYC rule same as pehle
        kyc = getattr(booking, "kyc_request", None)
        if kyc and kyc.status != KycStatus.APPROVED:
            return Response(
                {"detail": "KYC must be approved before confirming booking."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = booking.status
        old_kyc_status = booking.kyc_status

        now = timezone.now()
        booking.status = BookingStatus.BOOKED
        booking.booked_at = now
        booking.confirmed_by = user
        booking.save(update_fields=["status", "booked_at", "confirmed_by"])

        # 📝 Booking STATUS HISTORY
        BookingStatusHistory.objects.create(
            booking=booking,
            old_status=old_status,
            new_status=booking.status,
            old_kyc_status=old_kyc_status,
            new_kyc_status=booking.kyc_status,
            action="CONFIRM",
            reason=(request.data.get("reason") or "").strip(),
            changed_by=user,
        )

        # ---- FLAT / UNIT BOOKED ----
        # unit = booking.unit
        # if unit:
        #     try:
        #         unit.status = UnitStatus.BOOKED
        #     except Exception:
        #         unit.status = "BOOKED"
        #     unit.save(update_fields=["status"])

        #     inv = getattr(unit, "inventory_items", None)
        #     if inv:
        #         old_avail = inv.availability_status

        #         try:
        #             inv.unit_status = UnitStatus.BOOKED
        #             inv.availability_status = AvailabilityStatus.BOOKED
        #             inv.save(update_fields=["unit_status", "availability_status"])
        #         except Exception:
        #             inv.availability_status = AvailabilityStatus.BOOKED
        #             inv.save(update_fields=["availability_status"])

        #         InventoryStatusHistory.objects.create(
        #             inventory=inv,
        #             old_availability=old_avail,
        #             new_availability=inv.availability_status,
        #             reason=f"Booking #{booking.id} confirmed",
        #             changed_by=user,
        #         )

        unit = booking.unit
        if unit:
                unit.status = UnitStatus.BOOKED
                unit.save(update_fields=["status"])

                inv = getattr(unit, "inventory_items", None)
                if inv:
                    old_avail = inv.availability_status
                    inv.unit_status = UnitStatus.BOOKED
                    inv.availability_status = AvailabilityStatus.BOOKED
                    inv.save(update_fields=["unit_status", "availability_status"])

                    InventoryStatusHistory.objects.create(
                        inventory=inv,
                        old_availability=old_avail,
                        new_availability=inv.availability_status,
                        reason=f"Booking #{booking.id} confirmed",
                        changed_by=user,
                    )

        return Response(self.get_serializer(booking).data)



        # ---- PARKING SLOTS BOOKED ----
        for alloc in booking.parking_allocations.select_related("parking"):
            parking = alloc.parking
            if not parking:
                continue

            if parking.availability_status != AvailabilityStatus.BOOKED:
                old_parking_avail = parking.availability_status
                parking.availability_status = AvailabilityStatus.BOOKED
                parking.save(update_fields=["availability_status"])
                # Yahan bhi ParkingStatusHistory type ka log bana sakte ho future me

        serializer = self.get_serializer(booking)
        return Response(serializer.data)



    # @action(detail=True, methods=["post"], url_path="reject")
    # def reject_booking(self, request, pk=None):
    #     booking = self.get_object()
    #     user = request.user

    #     project = booking.project
    #     belongs_to_id = getattr(project, "belongs_to_id", None)
    #     if (
    #         belongs_to_id
    #         and belongs_to_id != user.id
    #         and not getattr(user, "is_superuser", False)
    #     ):
    #         return Response(
    #             {"detail": "You are not allowed to reject bookings for this project."},
    #             status=status.HTTP_403_FORBIDDEN,
    #         )

    #     if booking.status != BookingStatus.DRAFT:
    #         return Response(
    #             {"detail": "Only DRAFT bookings can be rejected."},
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     reason = (request.data.get("reason") or "").strip()

    #     with transaction.atomic():
    #         booking = (
    #             Booking.objects
    #             .select_for_update()
    #             .select_related("unit")
    #             .get(pk=booking.pk)
    #         )

    #         old_status = booking.status
    #         old_kyc_status = booking.kyc_status

    #         now = timezone.now()

    #         booking.status = BookingStatus.CANCELLED
    #         booking.cancelled_at = now
    #         if reason:
    #             booking.cancelled_reason = reason

    #         booking.save(
    #             update_fields=["status", "cancelled_at", "cancelled_reason"]
    #         )

    #         # 📝 Booking STATUS HISTORY
    #         BookingStatusHistory.objects.create(
    #             booking=booking,
    #             old_status=old_status,
    #             new_status=booking.status,
    #             old_kyc_status=old_kyc_status,
    #             new_kyc_status=booking.kyc_status,
    #             action="REJECT",
    #             reason=reason,
    #             changed_by=user,
    #         )


        # @action(detail=True, methods=["post"], url_path="reject")
        # def reject_booking(self, request, pk=None):
        #     booking = self.get_object()
        #     user = request.user

        #     project = booking.project
        #     belongs_to_id = project.belongs_to_id

        #     if not user.is_superuser:
        #         role = getattr(user, "role", None)
        #         role_code = role.upper() if isinstance(role, str) else getattr(role, "code", None)

        #         admin_id = user.id if role_code == "ADMIN" else getattr(user, "admin_id", None)

        #         if admin_id != belongs_to_id:
        #             return Response(
        #                 {"detail": "You are not allowed to reject bookings for this project."},
        #                 status=status.HTTP_403_FORBIDDEN,
        #             )

        #     if booking.status != BookingStatus.DRAFT:
        #         return Response(
        #             {"detail": "Only DRAFT bookings can be rejected."},
        #             status=status.HTTP_400_BAD_REQUEST,
        #         )

        #     reason = (request.data.get("reason") or "").strip()

        #     booking.status = BookingStatus.CANCELLED
        #     booking.cancelled_at = timezone.now()
        #     booking.cancelled_reason = reason
        #     booking.save(update_fields=["status", "cancelled_at", "cancelled_reason"])

        #     BookingStatusHistory.objects.create(
        #         booking=booking,
        #         old_status=BookingStatus.DRAFT,
        #         new_status=BookingStatus.CANCELLED,
        #         old_kyc_status=booking.kyc_status,
        #         new_kyc_status=booking.kyc_status,
        #         action="REJECT",
        #         reason=reason,
        #         changed_by=user,
        #     )

        #     return Response(self.get_serializer(booking).data)

        #     # ---- UNIT / INVENTORY AVAILABLE ----
        #     unit = booking.unit
        #     if unit:
        #         try:
        #             unit.status = UnitStatus.AVAILABLE
        #         except Exception:
        #             unit.status = "AVAILABLE"
        #         unit.save(update_fields=["status"])

        #         inv = getattr(unit, "inventory_items", None)
        #         if inv:
        #             old_avail = inv.availability_status

        #             try:
        #                 inv.unit_status = UnitStatus.AVAILABLE
        #                 inv.availability_status = AvailabilityStatus.AVAILABLE
        #                 inv.save(update_fields=["unit_status", "availability_status"])
        #             except Exception:
        #                 inv.availability_status = AvailabilityStatus.AVAILABLE
        #                 inv.save(update_fields=["availability_status"])

        #             InventoryStatusHistory.objects.create(
        #                 inventory=inv,
        #                 old_availability=old_avail,
        #                 new_availability=inv.availability_status,
        #                 reason=f"Booking #{booking.id} rejected – inventory released",
        #                 changed_by=user,
        #             )

        #     # ---- PARKING AVAILABLE ----
        #     for alloc in booking.parking_allocations.select_related("parking"):
        #         parking = alloc.parking
        #         if not parking:
        #             continue

        #         if parking.availability_status != AvailabilityStatus.AVAILABLE:
        #             parking.availability_status = AvailabilityStatus.AVAILABLE
        #             parking.save(update_fields=["availability_status"])
        #         # Future: ParkingStatusHistory me log kar sakte ho

        # serializer = self.get_serializer(booking)
        # return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        booking = self.get_object()
        user = request.user

        project = booking.project
        belongs_to_id = project.belongs_to_id

        # -------- PERMISSION CHECK --------
        if not user.is_superuser:
            role = getattr(user, "role", None)
            role_code = role.upper() if isinstance(role, str) else getattr(role, "code", None)

            admin_id = user.id if role_code == "ADMIN" else getattr(user, "admin_id", None)

            if admin_id != belongs_to_id:
                return Response(
                    {"detail": "You are not allowed to reject bookings for this project."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # -------- STATUS CHECK --------
        if booking.status != BookingStatus.DRAFT:
            return Response(
                {"detail": "Only DRAFT bookings can be rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reason = (request.data.get("reason") or "").strip()
        old_status = booking.status

        # -------- UPDATE BOOKING --------
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancelled_reason = reason
        booking.save(update_fields=["status", "cancelled_at", "cancelled_reason"])

        # -------- STATUS HISTORY --------
        BookingStatusHistory.objects.create(
            booking=booking,
            old_status=old_status,
            new_status=BookingStatus.CANCELLED,
            old_kyc_status=booking.kyc_status,
            new_kyc_status=booking.kyc_status,
            action="REJECT",
            reason=reason,
            changed_by=user,
        )

        # -------- UNIT / INVENTORY RELEASE --------
        unit = booking.unit
        if unit:
            unit.status = UnitStatus.AVAILABLE
            unit.save(update_fields=["status"])

            inv = getattr(unit, "inventory_items", None)
            if inv:
                old_avail = inv.availability_status
                inv.availability_status = AvailabilityStatus.AVAILABLE
                inv.save(update_fields=["availability_status"])

                InventoryStatusHistory.objects.create(
                    inventory=inv,
                    old_availability=old_avail,
                    new_availability=AvailabilityStatus.AVAILABLE,
                    reason=f"Booking #{booking.id} rejected – inventory released",
                    changed_by=user,
                )

        # -------- PARKING RELEASE --------
        for alloc in booking.parking_allocations.select_related("parking"):
            parking = alloc.parking
            if parking and parking.availability_status != AvailabilityStatus.AVAILABLE:
                parking.availability_status = AvailabilityStatus.AVAILABLE
                parking.save(update_fields=["availability_status"])

        return Response(self.get_serializer(booking).data, status=status.HTTP_200_OK)




    @action(detail=False, methods=["get"], url_path="pending-approvals")
    def pending_approvals(self, request):
        """
        GET /api/book/bookings/pending-approvals/

        - Sirf DRAFT bookings
        - Agar project.belongs_to use kar rahe ho, to
          sirf usi user ke projects ki bookings.
        - Is list se admin UI pe "Approve / Reject" dikh sakta hai.
        """
        user = request.user

        qs = self.get_queryset().filter(status=BookingStatus.DRAFT)

        # 👍 Project ownership filter (non-superadmin ke liye)
        if not getattr(user, "is_superuser", False):
            qs = qs.filter(project__belongs_to=user)

        # Optional: query param se project wise filter
        project_id = request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)

        # Optional: KYC filter, agar sirf KYC-linked DRAFT chahiye ho
        kyc_only = request.query_params.get("kyc_only")
        if kyc_only in ["1", "true", "True"]:
            qs = qs.filter(kyc_request__isnull=False)

        serializer = self.get_serializer(qs, many=True)
        return Response(self.get_serializer(qs, many=True).data)
   
   
