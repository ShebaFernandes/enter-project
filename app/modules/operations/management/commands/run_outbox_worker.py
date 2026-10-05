import time

from django.core.management.base import BaseCommand

from modules.operations.local_jobs import dispatch_local_event, require_local_worker, run_local_jobs
from modules.operations.workers import publish_batch


class Command(BaseCommand):
    help = "Run development outbox consumers, privacy exports and local mail delivery."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        require_local_worker()
        while True:
            published = publish_batch(dispatch_local_event)
            completed = run_local_jobs()
            if options["once"]:
                return
            if published == 0 and completed == 0:
                time.sleep(1)
