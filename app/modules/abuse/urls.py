from django.urls import path

from .views import AbuseOverrideView, StepUpChallengeView

urlpatterns = [
    path("security/step-up", StepUpChallengeView.as_view(), name="step-up"),
    path("security/abuse-overrides", AbuseOverrideView.as_view(), name="abuse-override"),
]
