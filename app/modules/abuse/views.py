from rest_framework.response import Response
from rest_framework.views import APIView


class StepUpChallengeView(APIView):
    def post(self, request):
        return Response({"challenge": "REAUTHENTICATE", "permanent_lockout": False}, status=202)
