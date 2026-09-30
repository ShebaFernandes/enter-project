from contextlib import contextmanager

from django.db import DatabaseError, connection, transaction


class SearchTemporarilyUnavailable(RuntimeError):
    pass


@contextmanager
def search_authorization_context(context: dict):
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.search_context_type', %s, true)", [context["type"]]
            )
            cursor.execute(
                "SELECT set_config('app.search_opening_id', %s, true)",
                [str(context.get("opening_id", ""))],
            )
    yield


def with_query_timeout(callback, *, milliseconds: int = 2500):
    try:
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = %s", [milliseconds])
            return callback()
    except DatabaseError as exc:
        raise SearchTemporarilyUnavailable("Search is temporarily unavailable.") from exc
