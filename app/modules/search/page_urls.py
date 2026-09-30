from django.urls import path

from .page_views import criteria_review_page, recruiter_search_page

urlpatterns = [
    path(
        "tenants/<uuid:tenant_id>/recruiter/search/",
        recruiter_search_page,
        name="recruiter-search-page",
    ),
    path(
        "tenants/<uuid:tenant_id>/recruiter/search/criteria-review/",
        criteria_review_page,
        name="criteria-review-page",
    ),
]
