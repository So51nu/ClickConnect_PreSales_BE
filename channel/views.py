# channel/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from leadmanage.models import LeadSource
from .models import (
    AgentType,
    
    PartnerTier,
    CrmIntegration,
    ChannelPartnerProfile,
    ChannelPartnerProjectAuthorization,
    ProjectAssignmentStatus,
    PartnerStatus,
    ChannelPartnerAttachment,
)
from .serializers import (
    ChannelPartnerMiniSerializer,
    ChannelPartnerQuickCreateSerializer,
)
from .utils import generate_unique_referral_code
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from accounts.models import Role
from clientsetup.models import Project
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from accounts.models import Role
from clientsetup.models import Project
from leadmanage.models import LeadSource   # <-- apne app ka sahi path laga lena
from .models import AgentType, PartnerTier, CrmIntegration
from .models import (
    AgentType,
    PartnerTier,
    CrmIntegration,
    ChannelPartnerProfile,
    ChannelPartnerProjectAuthorization,
    ProjectAssignmentStatus,
    PartnerStatus,
)
from .models import AgentType, PartnerTier, CrmIntegration
from .models import (
    AgentType,
    PartnerTier,
    CrmIntegration,
    ChannelPartnerProfile,
    ChannelPartnerProjectAuthorization,
    ChannelPartnerAttachment,
)
from .serializers import (
    AgentTypeSerializer,
    PartnerTierSerializer,
    CrmIntegrationSerializer,
    ChannelPartnerProfileListSerializer,
    ChannelPartnerProfileDetailSerializer,
    ChannelPartnerCreateUpdateSerializer,
    ChannelPartnerBulkCreateSerializer,
    SectionUpdateSerializer,
    ProjectAuthorizationSerializer,
    ProjectAuthorizationBulkUpdateSerializer,
    AttachmentSerializer,
)

from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.models import Role
from clientsetup.models import Project
from .models import ChannelPartnerProfile

User = get_user_model()


# ---------- Pagination ----------

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ---------- Master ViewSets ----------

class AgentTypeViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Agent Types
    """
    queryset = AgentType.objects.all().order_by('-created_at')
    serializer_class = AgentTypeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PartnerTierViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Partner Tiers
    """
    queryset = PartnerTier.objects.all().order_by('-created_at')
    serializer_class = PartnerTierSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CrmIntegrationViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for CRM Integrations
    """
    queryset = CrmIntegration.objects.all().order_by('-created_at')
    serializer_class = CrmIntegrationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ---------- Channel Partner ViewSet ----------

class ChannelPartnerViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for Channel Partners
    
    GET /api/channel/partners/ - List all partners (paginated)
    POST /api/channel/partners/ - Create new partner
    GET /api/channel/partners/{id}/ - Get partner detail
    PUT/PATCH /api/channel/partners/{id}/ - Update partner
    DELETE /api/channel/partners/{id}/ - Delete partner
    
    Additional endpoints:
    GET /api/channel/partners/by_source/{source_id}/ - Get partners by source
    POST /api/channel/partners/bulk_create/ - Bulk create partners
    PATCH /api/channel/partners/{id}/update_section/ - Update specific section
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = ChannelPartnerProfile.objects.select_related(
            'user', 'source', 'agent_type', 'partner_tier', 
            'crm_integration', 'parent_agent'
        ).prefetch_related(
            'project_authorizations__project',
            'attachments'
        ).order_by('-created_at')
        
        # Filter by status
        status_param = self.request.query_params.get('status', None)
        if status_param:
            queryset = queryset.filter(status=status_param)
        
        # Filter by onboarding status
        onboarding_status = self.request.query_params.get('onboarding_status', None)
        if onboarding_status:
            queryset = queryset.filter(onboarding_status=onboarding_status)
        
        # Search by name, email, or company
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(company_name__icontains=search)
            )
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ChannelPartnerProfileListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ChannelPartnerCreateUpdateSerializer
        elif self.action == 'bulk_create':
            return ChannelPartnerBulkCreateSerializer
        elif self.action == 'update_section':
            return SectionUpdateSerializer
        return ChannelPartnerProfileDetailSerializer
    
    @action(detail=False, methods=['get'], url_path='by-source/(?P<source_id>[^/.]+)')
    def by_source(self, request, source_id=None):
        """
        Get all channel partners by source ID
        GET /api/channel/partners/by-source/5/
        """
        partners = self.get_queryset().filter(source_id=source_id)
        
        page = self.paginate_queryset(partners)
        if page is not None:
            serializer = ChannelPartnerProfileDetailSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
        
        serializer = ChannelPartnerProfileDetailSerializer(partners, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """
        Bulk create multiple channel partners
        POST /api/channel/partners/bulk_create/
        
        Body:
        {
            "partners": [
                {
                    "email": "partner1@example.com",
                    "password": "secure123",
                    "first_name": "John",
                    ...
                },
                {
                    "email": "partner2@example.com",
                    ...
                }
            ]
        }
        
        Response:
        {
            "success": [
                {"index": 0, "id": 1, "email": "partner1@example.com"},
                {"index": 2, "id": 3, "email": "partner3@example.com"}
            ],
            "failed": [
                {"index": 1, "email": "partner2@example.com", "error": "Email already exists"}
            ]
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        results = serializer.save()
        
        return Response(results, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['patch'])
    def update_section(self, request, pk=None):
        """
        Update a specific section of channel partner
        PATCH /api/channel/partners/{id}/update_section/
        
        Body:
        {
            "section": "identity",  // identity, program, product_auth, lead_mgmt, compliance, operational, target, status
            "data": {
                "first_name": "John",
                "last_name": "Doe",
                ...
            }
        }
        """
        partner = self.get_object()
        serializer = self.get_serializer(partner, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return updated partner
        detail_serializer = ChannelPartnerProfileDetailSerializer(partner, context={'request': request})
        return Response(detail_serializer.data)


    @action(detail=False, methods=['get'], url_path='by-project')
    def by_project(self, request):
        """
        GET /api/channel/partners/by-project/?project_id=2[&source_id=15]

        Logic:
        - Base: saare ACTIVE CP jinke paas given project ka ACTIVE
          ChannelPartnerProjectAuthorization hai.
        - Agar source_id nahi diya:
            -> bas wohi list return.
        - Agar source_id diya:
            - LeadSource.for_cp == False -> empty list.
            - Agar for_cp == True and src.parent is NULL (main CP source):
                  -> base list hi return (pure project ke CP).
            - Agar for_cp == True and src.parent NOT NULL (sub-source):
                  -> sirf woh CP jinka profile.source == src.
        """

        project_id = request.query_params.get('project_id')
        source_id = request.query_params.get('source_id')

        if not project_id:
            return Response(
                {"detail": "project_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_qs = (
            ChannelPartnerProfile.objects
            .select_related('user', 'source')
            .filter(
                project_authorizations__project_id=project_id,
                project_authorizations__status=ProjectAssignmentStatus.ACTIVE,
                status=PartnerStatus.ACTIVE,
            )
            .distinct()
        )

        if not source_id:
            qs = base_qs
        else:
            try:
                src = LeadSource.objects.get(pk=source_id)
            except LeadSource.DoesNotExist:
                return Response(
                    {"detail": "Invalid source_id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not src.for_cp:
                # yeh source CP ke liye marked hi nahi hai
                qs = ChannelPartnerProfile.objects.none()
            else:
                if src.parent_id is None:
                    # parent CP source -> saare authorised CP
                    qs = base_qs
                else:
                    # sub-source -> sirf is source se linked CP
                    qs = base_qs.filter(source_id=src.id)

        page = self.paginate_queryset(qs)
        if page is not None:
            ser = ChannelPartnerMiniSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(ser.data)

        ser = ChannelPartnerMiniSerializer(qs, many=True, context={'request': request})
        return Response(ser.data)



    @action(detail=False, methods=['post'], url_path='quick-create')
    def quick_create(self, request):
        """
        POST /api/channel/partners/quick-create/

        Body example:
        {
          "project_id": 2,
          "partner_tier_id": 3,           // REQUIRED
          "source_id": 15,                // optional (must have for_cp=True)
          "name": "Atharva Broker",
          "email": "cp@example.com",
          "mobile_number": "9876543210",
          "company_name": "ABC Realty",
          "pan_number": "ABCDE1234F",
          "rera_number": "A1234567890"
        }
        """

        in_ser = ChannelPartnerQuickCreateSerializer(data=request.data)
        in_ser.is_valid(raise_exception=True)
        data = in_ser.validated_data

        project = get_object_or_404(Project, pk=data["project_id"])

        # ---- Source validate (optional) ----
        source = None
        source_id = data.get("source_id")
        if source_id is not None:
            source = get_object_or_404(LeadSource, pk=source_id)
            if not source.for_cp:
                return Response(
                    {"detail": "Selected source is not marked for channel partners (for_cp=False)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # ---- Partner tier (REQUIRED) ----
        partner_tier = get_object_or_404(PartnerTier, pk=data["partner_tier_id"])

        name = data["name"].strip()
        email = (data.get("email") or "").strip()
        mobile = (data.get("mobile_number") or "").strip()
        company_name = (data.get("company_name") or "").strip()
        pan_number = (data.get("pan_number") or "").strip()
        rera_number = (data.get("rera_number") or "").strip()

        # Name ko first/last me split kar lo
        parts = name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        # ---- User create ----
        username = email or mobile  # jo available ho
        if User.objects.filter(username=username).exists():
            return Response(
                {"detail": "A user with this email/mobile already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        temp_password = User.objects.make_random_password()

        user = User.objects.create_user(
            username=username,
            email=email or "",
            password=temp_password,
            first_name=first_name,
            last_name=last_name,
        )
        if hasattr(user, "role"):
            user.role = "CHANNEL_PARTNER"
            user.save()

        # ---- CP profile + referral code ----
        referral_code = generate_unique_referral_code()

        profile = ChannelPartnerProfile.objects.create(
            user=user,
            source=source,
            partner_tier=partner_tier,          # 👈 required field set
            mobile_number=mobile,
            company_name=company_name,
            pan_number=pan_number,
            rera_number=rera_number,
            referral_code=referral_code,
            status=PartnerStatus.ACTIVE,
            created_by=request.user,
            last_modified_by=request.user,
            last_modified_at=timezone.now(),
        )

        # ---- Project authorization ----
        ChannelPartnerProjectAuthorization.objects.get_or_create(
            channel_partner=profile,
            project=project,
            defaults={
                "status": ProjectAssignmentStatus.ACTIVE,
                "created_by": request.user,
            },
        )

        out = ChannelPartnerMiniSerializer(profile, context={'request': request}).data
        out["project_id"] = project.id
        out["source_id"] = source.id if source else None
        out["partner_tier_id"] = partner_tier.id
        out["temp_password"] = temp_password   # UI ko dikhana hai toh rakho

        return Response(out, status=status.HTTP_201_CREATED)


class ProjectAuthorizationViewSet(viewsets.ModelViewSet):
    """
    Manage project authorizations for channel partners
    
    GET /api/channel/partners/{partner_id}/project-authorizations/ - List authorizations
    POST /api/channel/partners/{partner_id}/project-authorizations/ - Add authorization
    DELETE /api/channel/project-authorizations/{id}/ - Remove authorization
    POST /api/channel/partners/{partner_id}/project-authorizations/bulk_update/ - Bulk toggle
    """
    serializer_class = ProjectAuthorizationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        partner_id = self.kwargs.get('partner_pk')
        if partner_id:
            return ChannelPartnerProjectAuthorization.objects.filter(
                channel_partner_id=partner_id
            ).select_related('project', 'channel_partner')
        return ChannelPartnerProjectAuthorization.objects.select_related(
            'project', 'channel_partner'
        )
    
    def perform_create(self, serializer):
        partner_id = self.kwargs.get('partner_pk')
        partner = get_object_or_404(ChannelPartnerProfile, id=partner_id)
        serializer.save(channel_partner=partner, created_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def bulk_update(self, request, partner_pk=None):
        """
        Bulk update project authorizations for a partner
        POST /api/channel/partners/{partner_id}/project-authorizations/bulk_update/
        
        Body:
        {
            "project_ids": [1, 2, 3],
            "start_date": "2025-01-01",
            "end_date": null,
            "status": "ACTIVE"
        }
        """
        partner = get_object_or_404(ChannelPartnerProfile, id=partner_pk)
        serializer = ProjectAuthorizationBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        project_ids = serializer.validated_data['project_ids']
        from clientsetup.models import Project
        
        # Remove authorizations not in the list
        partner.project_authorizations.exclude(project_id__in=project_ids).delete()
        
        # Add/update authorizations
        for project_id in project_ids:
            try:
                project = Project.objects.get(id=project_id)
                ChannelPartnerProjectAuthorization.objects.update_or_create(
                    channel_partner=partner,
                    project=project,
                    defaults={
                        'start_date': serializer.validated_data.get('start_date'),
                        'end_date': serializer.validated_data.get('end_date'),
                        'status': serializer.validated_data.get('status', 'ACTIVE'),
                        'created_by': request.user
                    }
                )
            except Project.DoesNotExist:
                pass
        
        # Return updated authorizations
        authorizations = partner.project_authorizations.all()
        result_serializer = ProjectAuthorizationSerializer(authorizations, many=True)
        return Response(result_serializer.data)


# ---------- Attachment ViewSet ----------

class AttachmentViewSet(viewsets.ModelViewSet):
    """
    Manage attachments for channel partners
    
    GET /api/channel/partners/{partner_id}/attachments/ - List attachments
    POST /api/channel/partners/{partner_id}/attachments/ - Upload attachment
    DELETE /api/channel/attachments/{id}/ - Delete attachment
    """
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        partner_id = self.kwargs.get('partner_pk')
        if partner_id:
            return ChannelPartnerAttachment.objects.filter(
                channel_partner_id=partner_id
            ).select_related('channel_partner')
        return ChannelPartnerAttachment.objects.select_related('channel_partner')
    
    def perform_create(self, serializer):
        partner_id = self.kwargs.get('partner_pk')
        partner = get_object_or_404(ChannelPartnerProfile, id=partner_id)
        serializer.save(channel_partner=partner, created_by=self.request.user)


class ChannelSetupBundleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        User = get_user_model()
        user = request.user
        user_role = getattr(user, "role", None)

        # ---- 1) Only ADMIN / staff allowed ----
        if not (user.is_staff or user_role == Role.ADMIN):
            return Response(
                {"detail": "Only admin users can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        admin_id = user.id

        # ---- 2) Projects that belong to this admin ----
        projects_qs = Project.objects.filter(
            belongs_to=user
        ).order_by("name")

        projects_payload = list(
            projects_qs.values("id", "name", "status", "approval_status")
        )

        project_ids = list(projects_qs.values_list("id", flat=True))

        # ---- 3) Parent Agents via Project Authorization ----
        # All ChannelPartnerProfile that:
        #   - have ACTIVE project_authorizations on any of these projects
        #   - and are ACTIVE themselves
        cp_profiles_qs = (
            ChannelPartnerProfile.objects.filter(
                project_authorizations__project_id__in=project_ids,
                project_authorizations__status=ProjectAssignmentStatus.ACTIVE,
                status=PartnerStatus.ACTIVE,
            )
            .select_related("user")
            .distinct()
        )

        def map_parent_agent(cp: ChannelPartnerProfile):
            u = cp.user
            full_name = (u.get_full_name() or "").strip()
            base_label = full_name or u.username or u.email
            company = (cp.company_name or "").strip()

            if company:
                label = f"{base_label} — {company}"
            else:
                label = base_label

            return {
                "id": cp.id,             # 👈 profile id, NOT user id (if you want user id, change to u.id)
                "user_id": u.id,
                "label": label,
                "role": getattr(u, "role", None),
            }

        parent_agents = [map_parent_agent(cp) for cp in cp_profiles_qs]

        # ---- 4) Sources (flat, as we did before) ----
        # sources_qs = (
        #     LeadSource.objects
        #     .filter(project__in=projects_qs)
        #     .select_related("project", "parent")
        #     .order_by("project_id", "parent_id", "name")
        # )

        # sources_payload = []
        # for src in sources_qs:
        #     sources_payload.append(
        #         {
        #             "id": src.id,
        #             "name": src.name,
        #             "parent_id": src.parent_id,
        #             "project_id": src.project_id,
        #             "project_name": src.project.name if src.project else None,
        #         }
        #     )

        sources_qs = (
            LeadSource.objects
            .filter(project__in=projects_qs)
            .select_related("project", "parent")
            .order_by("project_id", "parent_id", "name")
        )

        sources_payload = []
        seen = set()

        for src in sources_qs:
            # 👇 "exact same" ka matlab:
            # same project + same parent + same name (case-insensitive, trimmed)
            key = (
                src.project_id,
                src.parent_id or 0,
                (src.name or "").strip().lower(),
            )

            if key in seen:
                # duplicate -> skip
                continue

            seen.add(key)

            sources_payload.append(
                {
                    "id": src.id,
                    "name": src.name,
                    "parent_id": src.parent_id,
                    "project_id": src.project_id,
                    "project_name": src.project.name if src.project else None,
                    "for_cp": src.for_cp,   
                }
            )


        # ---- 5) Masters: AgentType / PartnerTier / CrmIntegration ----
        agent_types = list(
            AgentType.objects.filter(is_active=True)
            .order_by("name")
            .values("id", "name", "description", "is_active")
        )

        partner_tiers = list(
            PartnerTier.objects.filter(is_active=True)
            .order_by("code")
            .values("id", "code", "name", "description", "is_global", "is_active")
        )

        crm_integrations = list(
            CrmIntegration.objects.filter(is_active=True)
            .order_by("name")
            .values(
                "id",
                "name",
                "slug",
                "api_base_url",
                "auth_type",
                "description",
                "is_active",
            )
        )

        data = {
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user_role,
                "is_staff": user.is_staff,
            },
            "admin_id": admin_id,
            "parent_agents": parent_agents,
            "projects": projects_payload,
            "sources": sources_payload,
            "masters": {
                "agent_types": agent_types,
                "partner_tiers": partner_tiers,
                "crm_integrations": crm_integrations,
            },
        }
        return Response(data, status=200)


class AdminProjectChannelPartnersView(APIView):
    """
    GET /api/channel/admin-project-channel-partners/

    - Uses token auth (IsAuthenticated)
    - Only for role = ADMIN 
    - Returns all projects for that admin and all CPs linked to each project via LeadSource.

    Response shape:
    {
      "admin_id": 2,
      "projects": [
        {
          "id": 2,
          "name": "Anuj Residency",
          "status": "DRAFT",
          "approval_status": "PENDING",
          "channel_partners": [
            {
              "id": <cp_profile_id>,
              "user_id": <user_id>,
              "user_name": "CP Name (username)",
              "mobile_number": "...",
              "source_id": <lead_source_id>,
              "source_name": "Digital Ads",
              "onboarding_status": "PENDING",
              "status": "ACTIVE"
            },
            ...
          ]
        },
        ...
      ]
    }
    """

    permission_classes = [IsAuthenticated]

    # def get(self, request):
    #     user = request.user

    #     # ---- 1) Check admin role ----
    #     user_role = getattr(user, "role", None)
    #     if not (user_role == Role.ADMIN):
    #         return Response(
    #             {"detail": "Only admin users can access this endpoint."},
    #             status=status.HTTP_403_FORBIDDEN,
    #         )

    #     admin_id = user.id  # token se admin context

    #     # ---- 2) Get all projects for this admin ----
    #     # NOTE: adjust filter if your Project has a different field
    #     # e.g. Project.objects.filter(created_by_id=admin_id)
    #     projects_qs = Project.objects.filter(belongs_to=admin_id).order_by("name")

    #     # Prepare mapping: project_id -> payload
    #     proj_map = {
    #         p.id: {
    #             "id": p.id,
    #             "name": p.name,
    #             "status": getattr(p, "status", None),
    #             "approval_status": getattr(p, "approval_status", None),
    #             "channel_partners": [],
    #         }
    #         for p in projects_qs
    #     }

    #     if not proj_map:
    #         return Response(
    #             {
    #                 "admin_id": admin_id,
    #                 "projects": [],
    #             },
    #             status=200,
    #         )

    #     # ---- 3) Fetch all CP profiles whose source.project is in these projects ----
    #     cp_qs = (
    #         ChannelPartnerProfile.objects
    #         .select_related("user", "source", "source__project")
    #         .filter(source__project_id__in=proj_map.keys())
    #     )

    #     # ---- 4) Group CPs under respective projects ----
    #     for cp in cp_qs:
    #         project = cp.source.project if cp.source else None
    #         if not project:
    #             continue
    #         if project.id not in proj_map:
    #             continue

    #         u = cp.user
    #         full_name = (u.get_full_name() or "").strip()
    #         user_label = f"{full_name} ({u.username})" if full_name else u.username

    #         proj_map[project.id]["channel_partners"].append(
    #             {
    #                 "id": cp.id,
    #                 "user_id": u.id,
    #                 "user_name": user_label,
    #                 "mobile_number": cp.mobile_number,
    #                 "source_id": cp.source_id,
    #                 "source_name": cp.source.name if cp.source else None,
    #                 "onboarding_status": cp.onboarding_status,
    #                 "status": cp.status,
    #             }
    #         )

    #     # ---- 5) Final response ----
    #     return Response(
    #         {
    #             "admin_id": admin_id,
    #             "projects": list(proj_map.values()),
    #         },
    #         status=200,
    #     )

    

    
    def get(self, request):
        user = request.user

        # ---- 1) Resolve role safely ----
        role = getattr(user, "role", None)
        role_code = role.upper() if isinstance(role, str) else getattr(role, "code", None)

        # ---- 2) Allow ADMIN + FULL_CONTROL ----
        if role_code not in ("ADMIN", "FULL_CONTROL"):
            return Response(
                {"detail": "Only admin users can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---- 3) Resolve admin context ----
        if role_code == "ADMIN":
            admin_id = user.id
        else:  # FULL_CONTROL
            admin_id = getattr(user, "admin_id", None)

        if not admin_id:
            return Response(
                {"detail": "Admin context not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---- 4) Get all projects for this admin ----
        projects_qs = Project.objects.filter(belongs_to_id=admin_id).order_by("name")

        proj_map = {
            p.id: {
                "id": p.id,
                "name": p.name,
                "status": getattr(p, "status", None),
                "approval_status": getattr(p, "approval_status", None),
                "channel_partners": [],
            }
            for p in projects_qs
        }

        if not proj_map:
            return Response(
                {
                    "admin_id": admin_id,
                    "projects": [],
                },
                status=200,
            )

        # ---- 5) Fetch all CP profiles linked to these projects ----
        cp_qs = (
            ChannelPartnerProfile.objects
            .select_related("user", "source", "source__project")
            .filter(source__project_id__in=proj_map.keys())
        )

        # ---- 6) Group CPs under respective projects ----
        for cp in cp_qs:
            project = cp.source.project if cp.source else None
            if not project or project.id not in proj_map:
                continue

            u = cp.user
            full_name = (u.get_full_name() or "").strip()
            user_label = f"{full_name} ({u.username})" if full_name else u.username

            proj_map[project.id]["channel_partners"].append(
                {
                    "id": cp.id,
                    "user_id": u.id,
                    "user_name": user_label,
                    "mobile_number": cp.mobile_number,
                    "source_id": cp.source_id,
                    "source_name": cp.source.name if cp.source else None,
                    "onboarding_status": cp.onboarding_status,
                    "status": cp.status,
                }
            )

        # ---- 7) Final response ----
        return Response(
            {
                "admin_id": admin_id,
                "projects": list(proj_map.values()),
            },
            status=200,
        )

    