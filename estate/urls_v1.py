from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static  
from .pincode_lookup import PincodeLookupAPIView

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
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
