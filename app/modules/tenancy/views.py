from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.operations.concurrency import require_if_match, strong_etag
from modules.operations.idempotency import execute

from .business_units import create_business_unit, update_business_unit
from .models import BusinessUnit
from .serializers import BusinessUnitSerializer


class BusinessUnitCollectionView(APIView):
    def get(self, request, tenant_id):
        if request.tenant_id != tenant_id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        units = BusinessUnit.objects.filter(tenant_id=tenant_id).order_by("name")
        return Response(BusinessUnitSerializer(units, many=True).data)

    def post(self, request, tenant_id):
        def operation():
            serializer = BusinessUnitSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            unit = create_business_unit(
                membership=request.tenant_membership, **serializer.validated_data
            )
            return Response(BusinessUnitSerializer(unit).data, status=status.HTTP_201_CREATED)

        return execute(request, operation)


class BusinessUnitDetailView(APIView):
    def patch(self, request, tenant_id, business_unit_id):
        unit = BusinessUnit.objects.get(pk=business_unit_id, tenant_id=tenant_id)
        require_if_match(request.headers.get("If-Match"), unit, request.data)
        serializer = BusinessUnitSerializer(unit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        unit = update_business_unit(
            unit=unit, membership=request.tenant_membership, changes=serializer.validated_data
        )
        response = Response(BusinessUnitSerializer(unit).data)
        response["ETag"] = strong_etag(unit.pk, unit.version)
        return response
