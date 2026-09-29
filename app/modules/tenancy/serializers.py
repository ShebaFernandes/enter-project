from rest_framework import serializers

from .models import BusinessUnit, Tenant


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = (
            "id",
            "name",
            "slug",
            "status",
            "default_timezone",
            "retention_policy_version",
            "version",
        )
        read_only_fields = fields


class BusinessUnitSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = BusinessUnit
        fields = ("id", "tenant_id", "name", "description", "status", "version")
        read_only_fields = ("id", "tenant_id", "version")
