from auditlog.context import set_actor
from auditlog.middleware import AuditlogMiddleware as _AuditlogMiddleware
from django.utils.functional import SimpleLazyObject


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
