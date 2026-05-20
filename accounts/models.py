# accounts/models.py
from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """
    Perfil del usuario con datos KYC simulados.

    Extiende al `User` de Django via OneToOneField en lugar de modificar
    el modelo de auth: esto permite que un usuario pueda registrarse
    primero y completar el KYC después, sin afectar el flujo estándar
    de autenticación.

    Estados (máquina de estados del KYC, según la guía):
      PENDING_VERIFICATION -> recién creado, no puede apostar.
      VERIFIED             -> KYC aprobado, puede apostar.
      BLOCKED              -> bloqueado por el operador (fraude, irregularidad).
      SELF_EXCLUDED        -> el propio usuario se autoexcluye temporalmente
                              o indefinidamente (Nivel 1 punto 5).
    """

    class KycStatus(models.TextChoices):
        PENDING_VERIFICATION = 'PENDING_VERIFICATION', 'Pendiente de verificación'
        VERIFIED = 'VERIFIED', 'Verificado'
        BLOCKED = 'BLOCKED', 'Bloqueado'
        SELF_EXCLUDED = 'SELF_EXCLUDED', 'Autoexcluido'

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='profile'
    )
    dni = models.CharField(max_length=9, blank=True, default='', db_index=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    kyc_status = models.CharField(
        max_length=25,
        choices=KycStatus.choices,
        default=KycStatus.PENDING_VERIFICATION,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile {self.user.username} [{self.kyc_status}]"