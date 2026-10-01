import uuid

from django.core.management.base import BaseCommand
from django.utils import timezone

from modules.search.models import SearchWorkflowHandoff
from modules.tenancy.context import tenant_context
from modules.tenancy.rls import tenant_transaction


class Command(BaseCommand):
    help = "Remove expired encrypted search handoffs in one explicit tenant context."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", type=uuid.UUID, required=True)

    def handle(self, *args, **options):
        token = tenant_context.set(options["tenant"])
        try:
            with tenant_transaction():
                count, _ = SearchWorkflowHandoff.objects.filter(
                    tenant_id=options["tenant"], expires_at__lte=timezone.now()
                ).delete()
            self.stdout.write(f"Removed {count} expired handoffs.")
        finally:
            tenant_context.reset(token)
