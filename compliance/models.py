# compliance/models.py
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class SelfExclusion(models.Model):
    """
    Autoexclusión voluntaria del usuario del juego.

    La guía exige: "temporal (7/30/90 días) o indefinida; el usuario no
    puede revertirla antes del tiempo".

    Una autoexclusión está ACTIVA si:
      - kind = INDEFINITE y no fue revocada por admin (no implementado aún), o
      - kind = TEMPORARY_* y timezone.now() < ends_at.

    El usuario NO tiene método para revocarla: la única forma de "salir"
    de una temporal es esperar a que expire. Esto es una decisión de
    diseño psicológico, no técnico — exponer un endpoint de revoke
    derrotaría el propósito del control.
    """

    class Kind(models.TextChoices):
        TEMPORARY_7 = 'TEMPORARY_7', 'Temporal 7 días'
        TEMPORARY_30 = 'TEMPORARY_30', 'Temporal 30 días'
        TEMPORARY_90 = 'TEMPORARY_90', 'Temporal 90 días'
        INDEFINITE = 'INDEFINITE', 'Indefinida'

    # Mapa kind -> días. Centralizado para no esparcir mágicos por el código.
    DURATION_DAYS = {
        Kind.TEMPORARY_7: 7,
        Kind.TEMPORARY_30: 30,
        Kind.TEMPORARY_90: 90,
        # INDEFINITE no aparece aquí — se maneja como ends_at = None.
    }

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='self_exclusions'
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    starts_at = models.DateTimeField()
    # Nullable: INDEFINITE no tiene fecha de fin.
    ends_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Útil para el query "¿está activo este user?" — buscamos por user
        # y filtramos por (ends_at is null OR ends_at > now).
        indexes = [
            models.Index(fields=['user', 'ends_at']),
        ]

    def is_active(self) -> bool:
        """¿Esta autoexclusión está vigente en este instante?"""
        if self.ends_at is None:
            # INDEFINITE: siempre activa (hasta que un admin la revoque,
            # cosa que no implementamos en este ciclo).
            return True
        return timezone.now() < self.ends_at

    def __str__(self):
        end = self.ends_at.isoformat() if self.ends_at else 'indefinida'
        return f"SelfExclusion {self.user.username} ({self.kind}, hasta {end})"