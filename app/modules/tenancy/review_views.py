from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from modules.operations.concurrency import require_match, strong_etag
from modules.operations.idempotency import execute

from .access_reviews import complete_access_review, create_access_review
from .grants import revoke_emergency_access
from .models import EmergencyAccessRequest, TenantMembership
from .review_models import AccessReview


class AccessReviewCreateSerializer(serializers.Serializer):
    review_type = serializers.ChoiceField(choices=AccessReview.ReviewType.values)
    due_at = serializers.DateTimeField()
    reviewer_id = serializers.UUIDField(required=False)


class AccessReviewCompleteSerializer(serializers.Serializer):
    decisions = serializers.ListField(child=serializers.DictField(), min_length=1)


def review_projection(review: AccessReview) -> dict:
    return {
        "id": str(review.id),
        "review_type": review.review_type,
        "state": review.state,
        "population_hash": review.population_hash,
        "due_at": review.due_at.isoformat(),
        "completed_at": review.completed_at.isoformat() if review.completed_at else None,
        "decision_counts": review.decision_counts,
        "findings": review.findings,
        "revocations": review.revocations,
        "remediation_state": review.remediation_state,
        "version": review.version,
        "etag": strong_etag(review.id, review.version),
        "items": [
            {
                "id": str(item.id),
                "assignment_type": item.assignment_type,
                "subject_id": str(item.subject_id) if item.subject_id else None,
                "evidence": item.evidence,
                "decision": item.decision,
                "finding": item.finding,
                "remediation_state": item.remediation_state,
                "exception_expires_at": (
                    item.exception_expires_at.isoformat() if item.exception_expires_at else None
                ),
            }
            for item in review.items.all()
        ],
    }


class AccessReviewCollectionView(APIView):
    def get(self, request, tenant_id):
        from .access_reviews import _authorize

        _authorize(request.tenant_membership)
        reviews = AccessReview.objects.filter(tenant_id=tenant_id).prefetch_related("items")
        return Response([review_projection(item) for item in reviews])

    def post(self, request, tenant_id):
        def operation():
            serializer = AccessReviewCreateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            review = create_access_review(
                membership=request.tenant_membership,
                **serializer.validated_data,
            )
            response = Response(review_projection(review), status=status.HTTP_201_CREATED)
            response["ETag"] = strong_etag(review.id, review.version)
            return response

        return execute(request, operation)


class AccessReviewCompleteView(APIView):
    def post(self, request, tenant_id, access_review_id):
        review = AccessReview.objects.get(pk=access_review_id, tenant_id=tenant_id)
        serializer = AccessReviewCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require_match(
            request.headers.get("If-Match"),
            object_id=review.id,
            version=review.version,
            current=review_projection(review),
            attempted=serializer.validated_data,
        )

        def operation():
            completed = complete_access_review(
                membership=request.tenant_membership,
                review_id=review.id,
                if_match_version=review.version,
                decisions=serializer.validated_data["decisions"],
            )
            response = Response(review_projection(completed))
            response["ETag"] = strong_etag(completed.id, completed.version)
            return response

        return execute(request, operation)


class EmergencyAccessRevokeView(APIView):
    def post(self, request, tenant_id, emergency_request_id):
        if request.tenant_membership.role != TenantMembership.Role.TENANT_ADMIN:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied("Emergency access unavailable")

        def operation():
            access_request = EmergencyAccessRequest.objects.get(
                pk=emergency_request_id,
                tenant_id=tenant_id,
                status=EmergencyAccessRequest.Status.ACTIVE,
            )
            revoke_emergency_access(request=access_request, actor=request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)

        return execute(request, operation)
