from rest_framework import serializers

from .models import Opening


class OpeningSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(read_only=True)
    business_unit_id = serializers.UUIDField()
    hiring_team_ids = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Opening
        fields = (
            "id",
            "tenant_id",
            "business_unit_id",
            "title",
            "location",
            "work_mode",
            "employment_type",
            "description",
            "hiring_team_ids",
            "state",
            "version",
        )
        read_only_fields = ("id", "tenant_id", "state", "version")

    def get_hiring_team_ids(self, obj):
        return [item.membership_id for item in obj.hiring_team.all()]


class OpeningCreateSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(read_only=True)
    business_unit_id = serializers.UUIDField()
    hiring_team_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )

    class Meta:
        model = Opening
        fields = OpeningSerializer.Meta.fields
        read_only_fields = ("id", "tenant_id", "state", "version")


class OpeningPatchSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=1, max_length=300, required=False)
    description = serializers.CharField(max_length=20000, required=False, allow_blank=True)
    hiring_team_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    state = serializers.ChoiceField(choices=Opening.State.choices, required=False)
