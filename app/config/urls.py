from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from modules.operations.views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("", include("modules.candidate.page_urls")),
    path("", include("modules.privacy.page_urls")),
    path("api/v1/", include("modules.identity.urls")),
    path("api/v1/", include("modules.tenancy.urls")),
    path("api/v1/", include("modules.recruiting.urls")),
    path("api/v1/", include("modules.candidate.urls")),
    path("api/v1/", include("modules.privacy.urls")),
    path("api/v1/", include("modules.abuse.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
