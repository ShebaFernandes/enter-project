from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.operations.idempotency import execute

from .saved_searches import (
    create_saved_search,
    get_saved_search,
    list_saved_searches,
    project_saved_search,
)


class SavedSearchCreateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=200)
    search_id = serializers.UUIDField()

    def to_internal_value(self, data):
        unknown = set(data) - {"name", "search_id"}
        if unknown:
            raise serializers.ValidationError(
                {key: "This field is not permitted." for key in unknown}
            )
        return super().to_internal_value(data)


class SavedSearchCollectionView(APIView):
    def get(self, request, tenant_id):
        return Response(
            [
                project_saved_search(item)
                for item in list_saved_searches(membership=request.tenant_membership)
            ]
        )

    def post(self, request, tenant_id):
        def operation():
            serializer = SavedSearchCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            item = create_saved_search(
                membership=request.tenant_membership,
                **serializer.validated_data,
            )
            return Response(project_saved_search(item), status=status.HTTP_201_CREATED)

        return execute(request, operation)


class SavedSearchDetailView(APIView):
    def get(self, request, tenant_id, search_id):
        item = get_saved_search(
            membership=request.tenant_membership,
            search_id=search_id,
        )
        return Response(project_saved_search(item))
