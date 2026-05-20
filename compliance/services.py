# compliance/services.py
"""
Servicios de dominio para controles regulatorios (juego responsable).

Política: el resto del sistema (wallet, betting) consulta SOLO funciones
de este módulo para saber si una operación está permitida. No queremos
que `wallet/services.py` importe modelos de compliance directamente;
así, el día que cambie la lógica (p. ej. añadir bloqueo geográfico),
solo este archivo se toca.

Funciones expuestas:
  - is_user_self_excluded(user)          -> bool
  - create_self_exclusion(user, kind)    -> SelfExclusion
  - set_daily_deposit_limit(user, amount)   -> DepositLimit
  - set_weekly_deposit_limit(user, amount)  -> DepositLimit
  - set_monthly_deposit_limit(user, amount) -> DepositLimit
  - check_deposit_within_limits(user, amount) -> None (raises ValueError)
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from compliance.models import SelfExclusion


# ============================================================
# AUTOEXCLUSIÓN
# ============================================================

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
        models_q_active(now)
    ).exists()


def models_q_active(now):
    """Helper privado: construye el Q de exclusiones activas."""
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
        ends_at = now + timedelta(days=days)

    with transaction.atomic():
        return SelfExclusion.objects.create(
            user=user,
            kind=kind,
            starts_at=now,
            ends_at=ends_at,
        )


# ============================================================
# LÍMITES DE DEPÓSITO (cooldown asimétrico)
# ============================================================
#
# Regla de la guía: bajar el límite es instantáneo; subirlo requiere
# cooldown de 24h. La asimetría es intencional (protección psicológica).
# Ver ADR de juego responsable.
# ============================================================

def _set_deposit_limit(user: User, scope: str, amount: Decimal):
    """
    Helper interno: aplica la lógica asimétrica para los 3 scopes
    (daily / weekly / monthly).

    Regla:
      - Si NO hay límite previo (None) -> set instantáneo.
      - Si el nuevo amount <= límite actual -> bajada, set instantáneo
        (y se limpia cualquier pending de subida).
      - Si el nuevo amount > límite actual -> subida, queda como pending
        con timestamp now(); el efectivo no cambia hasta que pasen 24h.
    """
    # Import local: el modelo está en la misma app, no hay riesgo de ciclo,
    # pero mantenemos la convención de imports lazy para servicios.
    from compliance.models import DepositLimit

    if amount <= 0:
        raise ValueError(f"El límite debe ser mayor a cero. Recibido: {amount}")

    with transaction.atomic():
        limit_obj, _ = DepositLimit.objects.select_for_update().get_or_create(user=user)

        current = getattr(limit_obj, f'{scope}_limit')

        if current is None or amount <= current:
            # Bajada o set inicial: instantáneo.
            setattr(limit_obj, f'{scope}_limit', amount)
            # Limpiar cualquier pending de subida obsoleto.
            setattr(limit_obj, f'pending_{scope}', None)
            setattr(limit_obj, f'pending_{scope}_at', None)
        else:
            # Subida: queda pending por 24h.
            setattr(limit_obj, f'pending_{scope}', amount)
            setattr(limit_obj, f'pending_{scope}_at', timezone.now())

        limit_obj.save()
        return limit_obj


def set_daily_deposit_limit(user: User, amount: Decimal):
    """Define el límite diario de depósito del usuario."""
    return _set_deposit_limit(user, 'daily', amount)


def set_weekly_deposit_limit(user: User, amount: Decimal):
    """Define el límite semanal de depósito del usuario."""
    return _set_deposit_limit(user, 'weekly', amount)


def set_monthly_deposit_limit(user: User, amount: Decimal):
    """Define el límite mensual de depósito del usuario."""
    return _set_deposit_limit(user, 'monthly', amount)


# Ventanas móviles para cada scope (en días).
# Decisión: ventana móvil > ventana calendario. Ver ADR de juego responsable.
_WINDOW_DAYS = {
    'daily': 1,
    'weekly': 7,
    'monthly': 30,
}


def _sum_recharges_in_window(user: User, days: int) -> Decimal:
    """
    Suma las recargas del usuario en los últimos `days` (ventana móvil).

    Cuenta solo movimientos de tipo CREDIT en su cuenta WALLET,
    asociados a transacciones de kind RECHARGE.
    """
    # Import local: evita ciclos compliance <-> wallet.
    from wallet.models import LedgerEntry, Transaction, Account

    cutoff = timezone.now() - timedelta(days=days)
    total = LedgerEntry.objects.filter(
        account__user=user,
        account__type=Account.AccountType.WALLET,
        direction=LedgerEntry.Direction.CREDIT,
        transaction__kind=Transaction.TransactionKind.RECHARGE,
        transaction__created_at__gte=cutoff,
    ).aggregate(total=Sum('amount'))['total']

    return total or Decimal('0.0000')


def check_deposit_within_limits(user: User, amount: Decimal) -> None:
    """
    Verifica que una recarga de `amount` no exceda los límites
    (diario / semanal / mensual) en sus respectivas ventanas móviles.

    - Si el usuario no tiene `DepositLimit`, no hay nada que validar.
    - Para cada scope con límite configurado, suma sus recargas en la
      ventana y comprueba que `suma + amount <= límite_efectivo`.
    - Si alguno se excede, levanta ValueError con un mensaje claro.

    Llamado desde `wallet.services.execute_recharge` ANTES de cualquier
    movimiento contable: no queremos cuentas a medias.
    """
    from compliance.models import DepositLimit

    try:
        limit_obj = DepositLimit.objects.get(user=user)
    except DepositLimit.DoesNotExist:
        # Usuario sin configuración de límites: no hay nada que validar.
        return

    for scope, days in _WINDOW_DAYS.items():
        # Acceder via property `effective_*_limit` para que el modelo
        # promueva automáticamente cualquier pending que ya cumpla 24h.
        effective = getattr(limit_obj, f'effective_{scope}_limit')
        if effective is None:
            continue

        ya_recargado = _sum_recharges_in_window(user, days)
        if ya_recargado + amount > effective:
            raise ValueError(
                f"La recarga excede el límite {scope} configurado. "
                f"Límite: {effective}. Ya recargado en los últimos {days} día(s): "
                f"{ya_recargado}. Intentando recargar: {amount}."
            )