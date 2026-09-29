from rest_framework import serializers

from .models import DataRightsRequest


class RightsRequestCreateSerializer(serializers.Serializer):
    request_type = serializers.ChoiceField(choices=DataRightsRequest.RequestType.choices)
    scope = serializers.DictField(required=False)
    correction = serializers.DictField(required=False, allow_empty=False)
    confirm_consequences = serializers.BooleanField(required=False)
    step_up_proof = serializers.CharField(required=False, write_only=True)

    def validate(self, attrs):
        request_type = attrs["request_type"]
        if request_type == DataRightsRequest.RequestType.CORRECTION and not attrs.get("correction"):
            raise serializers.ValidationError({"correction": "Correction details are required."})
        if request_type == DataRightsRequest.RequestType.DELETE:
            if attrs.get("confirm_consequences") is not True or not attrs.get("step_up_proof"):
                raise serializers.ValidationError(
                    {"deletion": "Step-up proof and consequence confirmation are required."}
                )
        allowed = {"request_type", "scope"}
        if request_type == DataRightsRequest.RequestType.CORRECTION:
            allowed.add("correction")
        if request_type == DataRightsRequest.RequestType.DELETE:
            allowed.update({"confirm_consequences", "step_up_proof"})
        unknown = set(self.initial_data) - allowed
        if unknown:
            raise serializers.ValidationError(
                {key: "This field is not permitted." for key in unknown}
            )
        return attrs


class EscalationSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=True)
