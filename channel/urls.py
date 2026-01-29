# channel/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import (
    AgentTypeViewSet,
    PartnerTierViewSet,
    CrmIntegrationViewSet,
    ChannelPartnerViewSet,
    ProjectAuthorizationViewSet,
    AttachmentViewSet,ChannelSetupBundleView,AdminProjectChannelPartnersView
)

router = DefaultRouter()

router.register(r'agent-types', AgentTypeViewSet, basename='agent-type')
router.register(r'partner-tiers', PartnerTierViewSet, basename='partner-tier')
router.register(r'crm-integrations', CrmIntegrationViewSet, basename='crm-integration')

router.register(r'partners', ChannelPartnerViewSet, basename='channel-partner')

partners_router = routers.NestedDefaultRouter(router, r'partners', lookup='partner')
partners_router.register(r'project-authorizations', ProjectAuthorizationViewSet, basename='partner-project-auth')
partners_router.register(r'attachments', AttachmentViewSet, basename='partner-attachment')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(partners_router.urls)),
    path("setup-bundle/", ChannelSetupBundleView.as_view(), name="channel-setup-bundle"),
    path("admin-project-channel-partners/",AdminProjectChannelPartnersView.as_view(),name="admin-project-channel-partners",),
]

"""
Available endpoints:

Master Data:
- GET    /api/channel/agent-types/                     - List agent types
- POST   /api/channel/agent-types/                     - Create agent type
- GET    /api/channel/agent-types/{id}/                - Get agent type
- PUT    /api/channel/agent-types/{id}/                - Update agent type
- DELETE /api/channel/agent-types/{id}/                - Delete agent type

- GET    /api/channel/partner-tiers/                   - List partner tiers
- POST   /api/channel/partner-tiers/                   - Create partner tier
- GET    /api/channel/partner-tiers/{id}/              - Get partner tier
- PUT    /api/channel/partner-tiers/{id}/              - Update partner tier
- DELETE /api/channel/partner-tiers/{id}/              - Delete partner tier

- GET    /api/channel/crm-integrations/                - List CRM integrations
- POST   /api/channel/crm-integrations/                - Create CRM integration
- GET    /api/channel/crm-integrations/{id}/           - Get CRM integration
- PUT    /api/channel/crm-integrations/{id}/           - Update CRM integration
- DELETE /api/channel/crm-integrations/{id}/           - Delete CRM integration

Channel Partners:
- GET    /api/channel/partners/                        - List all partners (paginated)
- POST   /api/channel/partners/                        - Create new partner
- GET    /api/channel/partners/{id}/                   - Get partner detail
- PUT    /api/channel/partners/{id}/                   - Update partner (full)
- PATCH  /api/channel/partners/{id}/                   - Update partner (partial)
- DELETE /api/channel/partners/{id}/                   - Delete partner

Special Endpoints:
- GET    /api/channel/partners/by-source/{source_id}/  - Get partners by source
- POST   /api/channel/partners/bulk_create/            - Bulk create partners
- PATCH  /api/channel/partners/{id}/update_section/    - Update specific section

Project Authorizations:
- GET    /api/channel/partners/{partner_id}/project-authorizations/              - List authorizations
- POST   /api/channel/partners/{partner_id}/project-authorizations/              - Add authorization
- GET    /api/channel/partners/{partner_id}/project-authorizations/{id}/         - Get authorization
- PUT    /api/channel/partners/{partner_id}/project-authorizations/{id}/         - Update authorization
- DELETE /api/channel/partners/{partner_id}/project-authorizations/{id}/         - Delete authorization
- POST   /api/channel/partners/{partner_id}/project-authorizations/bulk_update/  - Bulk toggle projects

Attachments:
- GET    /api/channel/partners/{partner_id}/attachments/        - List attachments
- POST   /api/channel/partners/{partner_id}/attachments/        - Upload attachment
- GET    /api/channel/partners/{partner_id}/attachments/{id}/   - Get attachment
- DELETE /api/channel/partners/{partner_id}/attachments/{id}/   - Delete attachment

Query Parameters (for list endpoints):
- ?page=1&page_size=20                    - Pagination
- ?status=ACTIVE                          - Filter by status
- ?onboarding_status=PENDING              - Filter by onboarding status
- ?search=john                            - Search by name/email/company
"""
