from django.urls import path

from .views import StepUpChallengeView

urlpatterns = [path("security/step-up", StepUpChallengeView.as_view(), name="step-up")]
