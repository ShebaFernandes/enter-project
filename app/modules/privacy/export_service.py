from __future__ import annotations

import hashlib
import json
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from modules.candidate.services import profile_data
from modules.operations.crypto import decrypt, encrypt, safe_json

from .audit import audit_rights_action
from .models import DataRightsRequest, RightsExport


@transaction.atomic
def generate_export(export_id) -> RightsExport:
    export = (
        RightsExport.objects.select_for_update()
        .select_related("request__profile")
        .get(pk=export_id)
    )
    if export.request.request_type != DataRightsRequest.RequestType.EXPORT:
        raise ValidationError("Export request type is invalid.")
    export.state = RightsExport.State.GENERATING
    export.save(update_fields=("state",))
    payload = {
        "profile": profile_data(export.request.profile),
        "consents": list(
            export.request.profile.consents.values(
                "id",
                "purpose",
                "field_scope",
                "audience_scope",
                "notice_version",
                "captured_at",
                "expires_at",
                "withdrawn_at",
            )
        ),
        "rights_requests": list(
            export.request.profile.rights_requests.values(
                "id", "request_type", "state", "submitted_at", "completed_at"
            )
        ),
    }
    encoded = safe_json(payload)
    now = timezone.now()
    export.payload_ciphertext = encrypt(encoded)
    export.content_hash = hashlib.sha256(encoded.encode()).hexdigest()
    export.content_manifest = {"sections": sorted(payload), "complete": True}
    export.object_key = f"rights-exports/{export.request.profile_id}/{export.id}"
    export.state = RightsExport.State.READY
    export.ready_at = now
    export.expires_at = now + timedelta(hours=24)
    export.save()
    request = export.request
    request.state = DataRightsRequest.State.COMPLETED
    request.completed_at = now
    request.safe_detail = "Export ready for authenticated download"
    request.save(update_fields=("state", "completed_at", "safe_detail"))
    return export


@transaction.atomic
def download_export(*, identity, request: DataRightsRequest) -> dict[str, object]:
    if request.profile.identity_id != identity.id:
        raise PermissionDenied("Export unavailable")
    export = RightsExport.objects.select_for_update().filter(request=request).first()
    if (
        export is None
        or export.state != RightsExport.State.READY
        or export.expires_at is None
        or export.expires_at <= timezone.now()
        or not export.payload_ciphertext
    ):
        raise ValidationError("Export is unavailable or expired.")
    export.download_count += 1
    export.save(update_fields=("download_count",))
    audit_rights_action(actor=identity, request=request, action="RIGHTS_EXPORT_DOWNLOADED")
    return json.loads(decrypt(bytes(export.payload_ciphertext)))


def expire_exports() -> int:
    now = timezone.now()
    exports = RightsExport.objects.filter(state=RightsExport.State.READY, expires_at__lte=now)
    count = 0
    for export in exports:
        export.payload_ciphertext = None
        export.state = RightsExport.State.EXPIRED
        export.deleted_at = now
        export.save(update_fields=("payload_ciphertext", "state", "deleted_at"))
        count += 1
    return count
