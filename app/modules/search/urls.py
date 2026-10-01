from django.urls import path

from .criteria_views import execute_reviewed_search, interpret_search_view
from .handoff_views import ComparisonReturnView, HandoffDisplayView, HandoffView, RecentSearchView
from .saved_views import SavedSearchCollectionView, SavedSearchDetailView
from .views import candidate_detail

urlpatterns = [
    path(
        "tenants/<uuid:tenant_id>/search-handoffs/comparison-selection/return",
        ComparisonReturnView.as_view(),
    ),
    path(
        "tenants/<uuid:tenant_id>/search-handoffs/comparison-selection",
        HandoffView.as_view(),
        {"kind": "comparison-selection"},
    ),
    path(
        "tenants/<uuid:tenant_id>/search-handoffs/criteria-review",
        HandoffView.as_view(),
        {"kind": "criteria-review"},
    ),
    path(
        "tenants/<uuid:tenant_id>/search-handoffs/search-results",
        HandoffView.as_view(),
        {"kind": "search-results"},
    ),
    path(
        "tenants/<uuid:tenant_id>/search-handoffs/search-results/display",
        HandoffDisplayView.as_view(),
    ),
    path("tenants/<uuid:tenant_id>/recent-searches", RecentSearchView.as_view()),
    path("tenants/<uuid:tenant_id>/recent-searches/<uuid:search_id>", RecentSearchView.as_view()),
    path(
        "tenants/<uuid:tenant_id>/searches/interpret",
        interpret_search_view,
        name="search-interpret",
    ),
    path("tenants/<uuid:tenant_id>/searches", execute_reviewed_search, name="search-list"),
    path(
        "tenants/<uuid:tenant_id>/saved-searches",
        SavedSearchCollectionView.as_view(),
        name="saved-search-list",
    ),
    path(
        "tenants/<uuid:tenant_id>/saved-searches/<uuid:search_id>",
        SavedSearchDetailView.as_view(),
        name="saved-search-detail",
    ),
    path(
        "tenants/<uuid:tenant_id>/candidates/<uuid:candidate_id>",
        candidate_detail,
        name="search-candidate-detail",
    ),
]
