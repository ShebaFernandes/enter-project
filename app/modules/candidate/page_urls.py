from django.urls import path

from .views import candidate_profile_page

urlpatterns = [path("candidate/profile/", candidate_profile_page, name="candidate-profile-page")]
