from rest_framework.response import Response
from rest_framework.views import APIView

from .query_service import query_audit_events


class TenantAuditEventView(APIView):
    def get(self, request, tenant_id):
        limit = request.query_params.get("limit", "100")
        try:
            parsed_limit = int(limit)
        except ValueError:
            parsed_limit = 0
        return Response(
            query_audit_events(
                membership=request.tenant_membership,
                tenant_id=tenant_id,
                limit=parsed_limit,
            )
        )
