from django.urls import path

from .views import candidate_detail, execute_search, reopen_search, saved_searches

urlpatterns = [
    path("tenants/<uuid:tenant_id>/searches", execute_search, name="search-list"),
    path("tenants/<uuid:tenant_id>/saved-searches", saved_searches, name="saved-search-list"),
    path(
        "tenants/<uuid:tenant_id>/saved-searches/<uuid:search_id>",
        reopen_search,
        name="saved-search-detail",
    ),
    path(
        "tenants/<uuid:tenant_id>/candidates/<uuid:candidate_id>",
        candidate_detail,
        name="search-candidate-detail",
    ),
]
