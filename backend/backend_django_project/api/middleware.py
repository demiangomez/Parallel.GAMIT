from auditlog.context import set_actor
from auditlog.middleware import AuditlogMiddleware as _AuditlogMiddleware
from django.utils.functional import SimpleLazyObject
from django.db.utils import OperationalError as DatabaseOperationalError
from django.db import connections
from django.http import JsonResponse


class CustomAuditlogMiddleware(_AuditlogMiddleware):
    """
    This middleware fixes the issue with the auditlog middleware where the actor is not set correctly.
    Source: https://github.com/jazzband/django-auditlog/issues/115
    """

    def __call__(self, request):
        remote_addr = self._get_remote_addr(request)

        user = SimpleLazyObject(lambda: getattr(request, "user", None))

        context = set_actor(actor=user, remote_addr=remote_addr)

        with context:
            return self.get_response(request)


class DatabaseHealthCheckMiddleware:
    """
        The reason of this middleware is because DRF exception handler is unable
        to catch OperationError by itself.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        db_conn = connections['default']
        try:
            # Try executing a simple query
            with db_conn.cursor() as cursor:
                cursor.execute("SELECT 1")
        except DatabaseOperationalError:
            return JsonResponse(
                {
                    "type": "database_error",
                    "errors": [
                        {
                            "code": "database_error",
                            "detail": "Error when trying to connect to database",
                        }
                    ]
                },
                status=500
            )
        else:
            return self.get_response(request)
