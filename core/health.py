from __future__ import annotations

from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Endpoint simples para healthcheck de containers."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # pragma: no cover - defensivo
        return JsonResponse(
            {"status": "error", "database": str(exc)},
            status=503,
        )

    return JsonResponse({"status": "ok"})
