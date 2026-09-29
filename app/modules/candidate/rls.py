from __future__ import annotations

from django.db import connection, transaction


class CandidateIdentityRLSMiddleware:
    """Set a transaction-local subject for PostgreSQL candidate-owned policies."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with transaction.atomic():
            if connection.vendor == "postgresql":
                identity_id = str(request.user.pk) if request.user.is_authenticated else ""
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('app.identity_id', %s, true)", [identity_id])
            return self.get_response(request)
