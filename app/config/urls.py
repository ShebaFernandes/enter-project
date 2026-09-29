from django.urls import include, path

from modules.operations.views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("api/v1/", include("modules.identity.urls")),
    path("api/v1/", include("modules.tenancy.urls")),
    path("api/v1/", include("modules.recruiting.urls")),
    path("api/v1/", include("modules.abuse.urls")),
]
