# booking/views_kyc.py
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BookingKycRequest, KycStatus
from .serializers import (
    BookingKycRequestSerializer,
    BookingKycRequestCreateSerializer,
)
from .emails import send_kyc_request_email  # make sure this exists (see below)

# booking/views_kyc.py
from django.shortcuts import get_object_or_404

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BookingKycRequest, KycStatus, Booking
from .serializers import BookingKycRequestSerializer, BookingKycRequestCreateSerializer
from accounts.permissions import IsKycUser
from clientsetup.models import Project
# jaha bhi _project_ids_for_user defined hai, waha se import karo:
from salelead.views import _project_ids_for_user   # 👈 adjust path as per your code


class BookingKycRequestListForKycAPIView(APIView):
    """
    GET /api/book/kyc-requests/kyc-team/

    - Sirf KYC_TEAM role
    - User ke admin / projects ke hisaab se saare BookingKycRequest
    - Optional ?status=PENDING/APPROVED/REJECTED
    """
    permission_classes = [permissions.IsAuthenticated, IsKycUser]

    def get(self, request):
        user = request.user
        project_ids = _project_ids_for_user(user)

        qs = (
            BookingKycRequest.objects
            .select_related("project", "unit", "decided_by")
            .filter(project_id__in=project_ids)
            .order_by("-created_at")
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        serializer = BookingKycRequestSerializer(qs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BookingKycLinkToBookingAPIView(APIView):
    """
    POST /api/book/bookings/<booking_id>/link-kyc-request/
    Body:
    {
      "kyc_request_id": 123
    }

    - Sirf KYC_TEAM ko allowed
    - Security:
        - booking.project + kyc.project dono _project_ids_for_user me hone chahiye
    - Effect:
        - Booking.kyc_* fields ko KYC snapshot se sync karega
        - Optional: kyc.booking = booking (agar model me FK ho)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        user = request.user
        project_ids = _project_ids_for_user(user)

        booking = get_object_or_404(
            Booking.objects.select_related("project"),
            pk=booking_id,
            project_id__in=project_ids,
        )

        kyc_id = request.data.get("kyc_request_id")
        if not kyc_id:
            return Response(
                {"detail": "kyc_request_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        kyc = get_object_or_404(
            BookingKycRequest.objects.select_related("project", "decided_by"),
            pk=kyc_id,
        )

        # project access + consistency
        if kyc.project_id not in project_ids:
            return Response(
                {"detail": "You do not have access to this KYC request."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if booking.project_id != kyc.project_id:
            return Response(
                {"detail": "Booking and KYC request belong to different projects."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Snapshot into booking
        update_fields = ["kyc_status"]

        booking.kyc_status = kyc.status

        # (optional) submitted_at: agar KYC create time se set karna ho
        if hasattr(booking, "kyc_submitted_at") and not booking.kyc_submitted_at:
            if hasattr(kyc, "created_at"):
                booking.kyc_submitted_at = kyc.created_at
                update_fields.append("kyc_submitted_at")

        # Approved case -> more fields
        if kyc.status == KycStatus.APPROVED:
            if hasattr(booking, "kyc_deal_amount"):
                booking.kyc_deal_amount = getattr(kyc, "amount", None)
                update_fields.append("kyc_deal_amount")

            if hasattr(booking, "kyc_approved_at"):
                booking.kyc_approved_at = getattr(kyc, "decided_at", None)
                update_fields.append("kyc_approved_at")

            if hasattr(booking, "kyc_approved_by"):
                booking.kyc_approved_by = getattr(kyc, "decided_by", None)
                update_fields.append("kyc_approved_by")

        booking.save(update_fields=update_fields)

        # Optional: if BookingKycRequest model has booking FK:
        if hasattr(kyc, "booking"):
            if kyc.booking_id != booking.id:
                kyc.booking = booking
                kyc.save(update_fields=["booking"])

        return Response(
            {
                "detail": "KYC request linked to booking successfully.",
                "booking_id": booking.id,
                "kyc_request_id": kyc.id,
                "kyc_status": kyc.status,
            },
            status=status.HTTP_200_OK,
        )



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.utils import timezone

from booking.models import BookingKycRequest
from booking.serializers import BookingKycRequestSerializer
#from .permissions import IsKycUser


class BookingKycRequestApproveAPIView(APIView):
    """
    POST /api/book/kyc-requests/<id>/approve/

    - Only KYC_TEAM
    - Approves a pending KYC request
    """
    permission_classes = [permissions.IsAuthenticated, IsKycUser]

    def post(self, request, pk):
        user = request.user

        try:
            kyc_request = BookingKycRequest.objects.get(pk=pk)
        except BookingKycRequest.DoesNotExist:
            return Response(
                {"detail": "KYC request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if kyc_request.status != "PENDING":

            return Response(
                {"detail": "Only PENDING requests can be approved."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ approve
        kyc_request.status = "APPROVED"
        kyc_request.decided_by = user
        kyc_request.decided_at = timezone.now()
        kyc_request.decision_remarks = request.data.get(
            "decision_remarks", ""
        )
        kyc_request.save(
            update_fields=[
                "status",
                "decided_by",
                "decided_at",
                "decision_remarks",
            ]
        )

        serializer = BookingKycRequestSerializer(
            kyc_request, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)














class BookingKycRequestCreateAPIView(APIView):
    """
    POST /api/book/kyc-requests/
    Body: { "project_id":..., "unit_id":..., "amount":... }
    Called from BookingForm -> handleSendKycRequest.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BookingKycRequestCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        kyc = serializer.save()

        # send email with one-time link
        try:
            send_kyc_request_email(kyc)
        except Exception as exc:
            print("ERROR sending KYC email:", exc)

        data = BookingKycRequestSerializer(kyc).data
        return Response(data, status=status.HTTP_201_CREATED)


class BookingKycRequestDetailAPIView(APIView):
    """
    GET /api/book/kyc-requests/<pk>/
    Internal detail (for logged-in admin UI).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        kyc = get_object_or_404(BookingKycRequest, pk=pk)
        serializer = BookingKycRequestSerializer(kyc)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BookingKycOneTimeDetailAPIView(APIView):
    """
    GET /api/book/kyc-requests/one-time/<token>/
    - Used by magic link in email
    - No auth, token itself is proof
    """
    authentication_classes = []  # magic-link only
    permission_classes = []

    def get(self, request, token):
        kyc = get_object_or_404(BookingKycRequest, one_time_token=token)

        if kyc.token_used_at is not None:
            return Response(
                {"detail": "This link has already been used."},
                status=status.HTTP_410_GONE,
            )

        serializer = BookingKycRequestSerializer(kyc)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BookingKycDecisionAPIView(APIView):
    """
    POST /api/book/kyc-requests/<pk>/decision/
    Body:
    {
      "decision": "APPROVED" | "REJECTED",
      "remarks": "optional text",
      "token": "<magic_link_token>"   # when coming from email link
    }

    - If `token` diya hai -> magic link flow
    - Agar token nahi hai -> require logged-in admin user
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, pk):
        decision = (request.data.get("decision") or "").upper()
        remarks = (request.data.get("remarks") or "").strip()
        token = request.data.get("token")

        if decision not in (KycStatus.APPROVED, KycStatus.REJECTED):
            return Response(
                {"detail": "decision must be APPROVED or REJECTED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        kyc = get_object_or_404(BookingKycRequest, pk=pk)

        # --- validate token / auth combo ---
        if token:
            # email magic-link flow
            if kyc.one_time_token != token:
                return Response(
                    {"detail": "Invalid or mismatching token."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if kyc.token_used_at is not None:
                return Response(
                    {"detail": "This link has already been used."},
                    status=status.HTTP_410_GONE,
                )
        else:
            # normal admin UI flow -> require login
            if not request.user or not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication credentials were not provided."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

        # already decided?
        if kyc.status != KycStatus.PENDING:
            return Response(
                {"detail": f"KYC already {kyc.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # --- apply decision ---
        kyc.status = decision
        kyc.decision_remarks = remarks
        kyc.decided_at = timezone.now()

        if request.user and request.user.is_authenticated:
            kyc.decided_by = request.user

        # consume magic-link
        if token:
            kyc.token_used_at = timezone.now()
            kyc.one_time_token = None  # optional: clear token

        kyc.save()

        return Response(
            BookingKycRequestSerializer(kyc).data,
            status=status.HTTP_200_OK,
        )
	
