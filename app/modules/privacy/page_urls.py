from django.urls import path

from .views import rights_center_page

urlpatterns = [path("candidate/rights/", rights_center_page, name="candidate-rights-page")]
