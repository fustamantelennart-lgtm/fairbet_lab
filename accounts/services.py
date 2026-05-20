# accounts/services.py
"""
Servicios de dominio para la app `accounts`.

Política: la lógica de negocio del KYC (validación de DNI, edad mínima
y transición de estado) vive aquí, NO en el modelo ni en el view.
Esto mantiene los modelos como contenedores de datos y permite
orquestar validaciones complejas en un solo lugar atómico.
"""
from datetime import date
from django.contrib.auth.models import User
from django.db import transaction

from accounts.dni import es_dni_valido
from accounts.models import UserProfile


EDAD_MINIMA = 18


def _calcular_edad(fecha_nacimiento: date, hoy: date = None) -> int:
    """Edad cumplida al día de hoy, exacta por cumpleaños del año."""
    if hoy is None:
        hoy = date.today()
    años = hoy.year - fecha_nacimiento.year
    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        años -= 1
    return años


def verify_user_kyc(
    user: User,
    dni: str,
    fecha_nacimiento: date,
) -> UserProfile:
    """
    Verifica el KYC de un usuario y lo deja en estado VERIFIED si pasa.

    Validaciones (orden):
      1. El DNI tiene formato válido (9 chars: 8 dígitos + dígito verificador).
      2. El dígito verificador es matemáticamente coherente.
      3. El usuario es mayor o igual a 18 años cumplidos.

    Si alguna falla, levanta ValueError y NO se persiste el cambio de estado
    (atomic). El profile queda en PENDING_VERIFICATION.

    Returns:
        El UserProfile actualizado en estado VERIFIED.

    Raises:
        ValueError: si DNI es inválido o el usuario es menor de edad.
    """
    # 1. Validar DNI (formato + dígito verificador)
    if not es_dni_valido(dni):
        raise ValueError(
            f"El DNI '{dni}' es inválido: formato incorrecto o dígito verificador no coincide."
        )

    # 2. Validar mayoría de edad
    edad = _calcular_edad(fecha_nacimiento)
    if edad < EDAD_MINIMA:
        raise ValueError(
            f"El usuario debe ser mayor de {EDAD_MINIMA} años. Edad calculada: {edad}."
        )

    # 3. Persistir cambios atómicamente
    with transaction.atomic():
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.dni = dni
        profile.fecha_nacimiento = fecha_nacimiento
        profile.kyc_status = UserProfile.KycStatus.VERIFIED
        profile.save(update_fields=['dni', 'fecha_nacimiento', 'kyc_status', 'updated_at'])
        return profile