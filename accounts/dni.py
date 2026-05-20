# accounts/dni.py
"""
Algoritmo del dígito verificador del DNI peruano.

Módulo 11 con pesos descendentes [3, 2, 7, 6, 5, 4, 3, 2] aplicados a
los 8 dígitos del DNI. La tabla de mapeo del residuo al carácter de
verificación es la documentada por Reniec / Excel Negocios:
  residuo 0  -> 'K'   (caso especial)
  residuo 1  -> '0'
  residuo 2  -> '1'
  ...
  residuo 10 -> '9'

Esta función es PURA: no toca Django, no toca DB, no tiene side effects.
Por eso vive en su propio módulo y se testea de forma independiente.
"""

PESOS = [3, 2, 7, 6, 5, 4, 3, 2]
# Índice = residuo (mod 11). Valor = carácter del dígito verificador.
TABLA_DV = ['K', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']


def calcular_digito_verificador(dni_8: str) -> str:
    """
    Calcula el dígito verificador para los 8 dígitos base del DNI.

    Args:
        dni_8: string de exactamente 8 caracteres, todos dígitos.

    Returns:
        Un único carácter (0-9 o 'K') que es el dígito verificador.

    Raises:
        ValueError: si dni_8 no tiene 8 caracteres o contiene no-dígitos.
    """
    if not isinstance(dni_8, str) or len(dni_8) != 8:
        raise ValueError(
            f"El DNI base debe tener exactamente 8 dígitos. Recibido: {dni_8!r}"
        )

    if not dni_8.isdigit():
        raise ValueError(
            f"El DNI base solo puede contener dígitos. Recibido: {dni_8!r}"
        )

    suma = sum(int(d) * p for d, p in zip(dni_8, PESOS))
    residuo = suma % 11
    return TABLA_DV[residuo]


def es_dni_valido(dni_9: str) -> bool:
    """
    Valida un DNI completo de 9 caracteres: 8 dígitos + 1 dígito verificador.

    Returns True si el dígito verificador es coherente con los primeros 8.
    """
    if not isinstance(dni_9, str) or len(dni_9) != 9:
        return False

    base = dni_9[:8]
    dv_provisto = dni_9[8].upper()

    try:
        dv_calculado = calcular_digito_verificador(base)
    except ValueError:
        return False

    return dv_provisto == dv_calculado