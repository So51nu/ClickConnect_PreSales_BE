from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static  
from .pincode_lookup import PincodeLookupAPIView
from django.urls import path
from salelead.meta_webhook import meta_webhook
from salelead.integrations.views import ingest_opportunity
from .views_static import privacy_policy, data_deletion

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/accounts/", include("accounts.urls")),
    path("api/client/", include("clientsetup.urls")),
    path("api/setup/", include("setup.urls")),
    path("api/leadManagement/", include("leadmanage.urls")),
    path("api/sales/", include("salelead.urls")),
    path("api/costsheet/", include("costsheet.urls")),
    path("api/channel/", include("channel.urls")),
    path("api/book/", include("booking.urls")),
    path("api/dashboard/", include("dashboard.urls")),   
    path("api/utils/pincode-lookup/", PincodeLookupAPIView.as_view(), name="pincode-lookup"),
    path("api/webhooks/meta/", meta_webhook),

    # ✅ Generic integrations (MagicBricks, 99acres, etc.)
    path(
        "api/sales/integrations/opportunities/<str:source_system>/",
        ingest_opportunity,
        name="ingest-opportunity",
    ),
    path("api/sales/integrations/opportunities/<str:source_system>", ingest_opportunity),
    path("privacy-policy/", privacy_policy),
    path("data-deletion/", data_deletion),
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
