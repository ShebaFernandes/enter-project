from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.operations.idempotency import execute

from .context import effective_role
from .policy import AuthorizationRequest, authorize
from .provisioning import provision_tenant
from .serializers import TenantSerializer


class TenantProvisionSerializer(serializers.Serializer):
    contracted_company_name = serializers.CharField(min_length=1, max_length=300)
    legal_boundary_reference = serializers.CharField(min_length=1, max_length=300)


class TenantProvisionView(APIView):
    def post(self, request):
        def operation():
            authorize(
                AuthorizationRequest(
                    action="platform.tenant.provision",
                    role=effective_role(request),
                    tenant_id=None,
                )
            )
            serializer = TenantProvisionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            tenant = provision_tenant(actor=request.user, **serializer.validated_data)
            return Response(TenantSerializer(tenant).data, status=status.HTTP_201_CREATED)

        return execute(request, operation)
