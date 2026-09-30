import json

from django.core.management.base import BaseCommand

from modules.identity.local_auth import TOKEN_TTL_SECONDS, issue_local_recruiter_bootstrap


class Command(BaseCommand):
    help = "Create a one-time local/test synthetic recruiter session URL."

    def add_arguments(self, parser):
        parser.add_argument("--base-url", default="http://127.0.0.1:8000")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        issued = issue_local_recruiter_bootstrap()
        url = (
            f"{str(options['base_url']).rstrip('/')}"
            f"/api/v1/__local__/synthetic-recruiter-session?token={issued.token}"
        )
        payload = {
            "url": url,
            "tenant_id": issued.tenant_id,
            "recruiter_id": issued.recruiter_id,
            "candidate_id": issued.candidate_id,
            "expires_in_seconds": TOKEN_TTL_SECONDS,
        }
        if options["json"]:
            self.stdout.write(json.dumps(payload, sort_keys=True))
        else:
            self.stdout.write("Open this one-time synthetic recruiter URL within 10 minutes:")
            self.stdout.write(url)
