# compliance/models.py
from datetime import timedelta
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class SelfExclusion(models.Model):
    """
    Autoexclusión voluntaria del usuario del juego.
    (... contenido existente sin cambios ...)
    """

    class Kind(models.TextChoices):
        TEMPORARY_7 = 'TEMPORARY_7', 'Temporal 7 días'
        TEMPORARY_30 = 'TEMPORARY_30', 'Temporal 30 días'
        TEMPORARY_90 = 'TEMPORARY_90', 'Temporal 90 días'
        INDEFINITE = 'INDEFINITE', 'Indefinida'

    DURATION_DAYS = {
        Kind.TEMPORARY_7: 7,
        Kind.TEMPORARY_30: 30,
        Kind.TEMPORARY_90: 90,
    }

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='self_exclusions'
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'ends_at']),
        ]

    def is_active(self) -> bool:
        if self.ends_at is None:
            return True
        return timezone.now() < self.ends_at

    def __str__(self):
        end = self.ends_at.isoformat() if self.ends_at else 'indefinida'
        return f"SelfExclusion {self.user.username} ({self.kind}, hasta {end})"


# === AÑADIR DESDE AQUÍ ===

class DepositLimit(models.Model):
    """
    Límites de depósito (recarga) configurables por el usuario.

    Política de modificación (regla asimétrica, exigida por la guía):
      - Bajar un límite (o establecerlo desde None) es INSTANTÁNEO:
        protección al usuario.
      - Subir un límite requiere COOLDOWN de 24h: protección psicológica
        para evitar decisiones impulsivas.

    Implementación del cooldown:
      Cuando el usuario pide subir el límite (p.ej. 100 -> 500), guardamos
      `pending_daily=500` + `pending_daily_at=now()`, pero el valor que
      el sistema OBEDECE sigue siendo `daily_limit=100`. La propiedad
      `effective_daily_limit` promueve automáticamente el pending al
      consultarse si han pasado 24h desde `pending_daily_at`.

    `None` en un límite significa "sin límite" (la guía dice
    "configurable por el usuario", no exige que el operador imponga
    valores por defecto).
    """

    COOLDOWN = timedelta(hours=24)

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='deposit_limit'
    )

    # Límites VIGENTES
    daily_limit = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    weekly_limit = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    monthly_limit = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    # Subidas pendientes (esperan 24h para activarse)
    pending_daily = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    pending_daily_at = models.DateTimeField(null=True, blank=True)
    pending_weekly = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    pending_weekly_at = models.DateTimeField(null=True, blank=True)
    pending_monthly = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    pending_monthly_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _promote_if_cooldown_done(self, scope: str) -> None:
        """
        Si el pending de `scope` (daily/weekly/monthly) tiene >24h,
        promovemos el pending al límite real y limpiamos.

        Llamado por las properties effective_*_limit antes de retornar.
        Tiene side effect en la DB (save), por diseño: lo natural
        es que el sistema esté siempre en estado coherente sin necesidad
        de un cron.
        """
        pending = getattr(self, f'pending_{scope}')
        pending_at = getattr(self, f'pending_{scope}_at')
        if pending is None or pending_at is None:
            return

        if timezone.now() - pending_at >= self.COOLDOWN:
            setattr(self, f'{scope}_limit', pending)
            setattr(self, f'pending_{scope}', None)
            setattr(self, f'pending_{scope}_at', None)
            self.save(update_fields=[
                f'{scope}_limit',
                f'pending_{scope}',
                f'pending_{scope}_at',
                'updated_at',
            ])

    @property
    def effective_daily_limit(self):
        self._promote_if_cooldown_done('daily')
        return self.daily_limit

    @property
    def effective_weekly_limit(self):
        self._promote_if_cooldown_done('weekly')
        return self.weekly_limit

    @property
    def effective_monthly_limit(self):
        self._promote_if_cooldown_done('monthly')
        return self.monthly_limit

    def __str__(self):
        return (
            f"DepositLimit {self.user.username} "
            f"(D={self.daily_limit}, W={self.weekly_limit}, M={self.monthly_limit})"
        )