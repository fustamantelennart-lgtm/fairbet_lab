# compliance/services.py
"""
Servicios de dominio para controles regulatorios (juego responsable).

Política: el resto del sistema (wallet, betting) consulta SOLO funciones
de este módulo para saber si una operación está permitida. No queremos
que `wallet/services.py` importe modelos de compliance directamente;
así, el día que cambie la lógica (p. ej. añadir bloqueo geográfico),
solo este archivo se toca.
"""
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from compliance.models import SelfExclusion


def is_user_self_excluded(user: User) -> bool:
    """
    True si el usuario tiene al menos una autoexclusión activa en este momento.

    Una exclusión está activa si:
      - kind = INDEFINITE (ends_at IS NULL), o
      - ends_at > now()

    Se evalúa al instante de la consulta — el paso del tiempo "desactiva"
    las temporales sin necesidad de un job de fondo.
    """
    now = timezone.now()
    return SelfExclusion.objects.filter(user=user).filter(
        # Activa si: indefinida (ends_at NULL) o no expirada
        models_q_active(now)
    ).exists()


def models_q_active(now):
    """Helper privado: construye el Q de exclusiones activas."""
    from django.db.models import Q
    return Q(ends_at__isnull=True) | Q(ends_at__gt=now)


def create_self_exclusion(user: User, kind: str) -> SelfExclusion:
    """
    Crea una autoexclusión para el usuario.

    Calcula `ends_at` automáticamente para los kinds TEMPORARY_*.
    Para INDEFINITE, `ends_at = None`.

    Nota: NO valida si el usuario ya tiene una activa. La guía permite
    múltiples (p.ej., extender una autoexclusión solicitando una nueva
    más larga). El método `is_user_self_excluded` cubre el OR de todas.
    """
    now = timezone.now()

    if kind == SelfExclusion.Kind.INDEFINITE:
        ends_at = None
    else:
        days = SelfExclusion.DURATION_DAYS.get(kind)
        if days is None:
            raise ValueError(f"Tipo de autoexclusión desconocido: {kind!r}")
        from datetime import timedelta
        ends_at = now + timedelta(days=days)

    with transaction.atomic():
        return SelfExclusion.objects.create(
            user=user,
            kind=kind,
            starts_at=now,
            ends_at=ends_at,
        )