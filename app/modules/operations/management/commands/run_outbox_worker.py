import json
import time

from django.core.management.base import BaseCommand

from modules.operations.workers import publish_batch


class Command(BaseCommand):
    help = "Run the local transactional-outbox relay."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        def local_publisher(envelope):
            self.stdout.write(json.dumps(envelope, sort_keys=True))

        while True:
            published = publish_batch(local_publisher)
            if options["once"]:
                return
            if published == 0:
                time.sleep(1)
