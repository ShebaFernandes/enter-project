from rest_framework import serializers


class ContextSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["AD_HOC", "OPENING"])
    opening_id = serializers.UUIDField(required=False)

    def validate(self, attrs):
        if attrs["type"] == "AD_HOC" and "opening_id" in attrs:
            raise serializers.ValidationError({"opening_id": "AD_HOC must not contain opening_id."})
        if attrs["type"] == "OPENING" and "opening_id" not in attrs:
            raise serializers.ValidationError({"opening_id": "OPENING requires opening_id."})
        return attrs


class GroupSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    purpose = serializers.ChoiceField(choices=["REQUIREMENT", "PREFERENCE", "EXCLUSION"])
    operator = serializers.ChoiceField(choices=["ANY", "ALL"])
    label = serializers.CharField(  # type: ignore[assignment]
        max_length=200, required=False, allow_blank=True, allow_null=True
    )

    def to_internal_value(self, data):
        unknown = set(data) - {"id", "purpose", "operator", "label"}
        if unknown:
            raise serializers.ValidationError(
                {key: "This field is not permitted." for key in unknown}
            )
        return super().to_internal_value(data)


class CriterionSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    group_id = serializers.UUIDField()
    field = serializers.CharField(max_length=100)
    operator = serializers.ChoiceField(
        choices=["EQ", "NE", "LT", "LTE", "GT", "GTE", "IN", "NOT_IN", "CONTAINS", "EXISTS"]
    )
    value = serializers.JSONField()

    def to_internal_value(self, data):
        unknown = set(data) - {"id", "group_id", "field", "operator", "value"}
        if unknown:
            raise serializers.ValidationError(
                {key: "This field is not permitted." for key in unknown}
            )
        return super().to_internal_value(data)


class SearchCriteriaSerializer(serializers.Serializer):
    context = ContextSerializer()  # type: ignore[assignment]
    groups = GroupSerializer(many=True, min_length=1)  # type: ignore[call-arg]
    criteria = CriterionSerializer(many=True, min_length=1)  # type: ignore[call-arg]
    cursor = serializers.CharField(required=False, allow_null=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=25)

    def validate(self, attrs):
        unknown = set(self.initial_data) - {"context", "groups", "criteria", "cursor", "limit"}
        if unknown:
            raise serializers.ValidationError(
                {key: "This field is not permitted." for key in unknown}
            )
        from .engine import CriteriaValidationError, validate_criteria

        try:
            validate_criteria(attrs["groups"], attrs["criteria"])
        except CriteriaValidationError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return attrs


class SavedSearchInputSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=1, max_length=200)
    search_id = serializers.UUIDField()
