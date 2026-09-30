from django.urls import path

from .page_views import recruiter_search_page

urlpatterns = [
    path(
        "tenants/<uuid:tenant_id>/recruiter/search/",
        recruiter_search_page,
        name="recruiter-search-page",
    )
]
