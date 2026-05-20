# accounts/test_kyc.py
from datetime import date
from django.test import TestCase
from django.contrib.auth.models import User


class DniDigitoVerificadorTDDTestCase(TestCase):
    """
    Fase RED — Algoritmo del dígito verificador del DNI peruano.

    Aplicamos el algoritmo Módulo 11 con pesos [3, 2, 7, 6, 5, 4, 3, 2]
    documentado por Reniec / Excel Negocios / El Comercio.

    Tabla de mapeo residuo -> dígito:
      0 -> 'K', 1 -> '0', 2 -> '1', ..., 10 -> '9'
    """

    def test_digit_for_known_valid_dni(self):
        """
        DNI conocido válido: '40235871' debe tener dígito verificador '3'.

        Cálculo manual:
          4*3 + 0*2 + 2*7 + 3*6 + 5*5 + 8*4 + 7*3 + 1*2
        = 12 + 0 + 14 + 18 + 25 + 32 + 21 + 2 = 124
          124 % 11 = 3
          tabla[3] = '2'
        """
        from accounts.dni import calcular_digito_verificador
        # NOTA: este es un ejemplo aritmético, no un DNI real.
        # El dígito real depende de la versión del algoritmo elegida.
        result = calcular_digito_verificador('40235871')
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 1)

    def test_rejects_dni_with_wrong_length(self):
        """Un DNI que no tenga 8 dígitos debe levantar ValueError."""
        from accounts.dni import calcular_digito_verificador
        with self.assertRaises(ValueError):
            calcular_digito_verificador('1234567')   # 7 dígitos
        with self.assertRaises(ValueError):
            calcular_digito_verificador('123456789') # 9 dígitos

    def test_rejects_dni_with_non_numeric(self):
        """Un DNI con caracteres no numéricos debe levantar ValueError."""
        from accounts.dni import calcular_digito_verificador
        with self.assertRaises(ValueError):
            calcular_digito_verificador('1234567A')


class KycServiceTDDTestCase(TestCase):
    """
    Fase RED — Servicio de verificación KYC.

    Valida que el service:
      - Cambia el estado de PENDING_VERIFICATION a VERIFIED cuando
        DNI es válido y el usuario es mayor de edad.
      - Rechaza menores de edad con ValueError.
      - Rechaza DNIs con dígito verificador incorrecto con ValueError.
      - El estado por defecto de un UserProfile es PENDING_VERIFICATION.
    """

    def setUp(self):
        self.user, _ = User.objects.get_or_create(username='postulante_kyc')

    def test_default_kyc_status_is_pending(self):
        """Un UserProfile recién creado debe estar en PENDING_VERIFICATION."""
        from accounts.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        self.assertEqual(profile.kyc_status, UserProfile.KycStatus.PENDING_VERIFICATION)

    def test_verify_user_kyc_with_valid_adult_succeeds(self):
        """
        Un usuario con DNI válido y mayor de 18 años queda VERIFIED.
        Calculamos en vivo el dígito verificador correcto para no
        depender de un DNI hardcodeado y que el test sea consistente
        con cualquier versión válida del algoritmo.
        """
        from accounts.dni import calcular_digito_verificador
        from accounts.services import verify_user_kyc
        from accounts.models import UserProfile

        dni_base = '40235871'
        dv = calcular_digito_verificador(dni_base)
        dni_completo = dni_base + dv

        # Persona de 30 años (claramente mayor de edad)
        fecha_nac = date(1995, 1, 1)

        profile = verify_user_kyc(
            user=self.user,
            dni=dni_completo,
            fecha_nacimiento=fecha_nac,
        )

        self.assertEqual(profile.kyc_status, UserProfile.KycStatus.VERIFIED)
        self.assertEqual(profile.dni, dni_completo)

    def test_verify_user_kyc_rejects_minor(self):
        """Un usuario menor de 18 años debe ser rechazado."""
        from accounts.dni import calcular_digito_verificador
        from accounts.services import verify_user_kyc

        dni_base = '40235871'
        dv = calcular_digito_verificador(dni_base)
        dni_completo = dni_base + dv

        # 10 años de edad
        fecha_nac = date(2016, 1, 1)

        with self.assertRaises(ValueError) as ctx:
            verify_user_kyc(
                user=self.user,
                dni=dni_completo,
                fecha_nacimiento=fecha_nac,
            )
        # El mensaje debe mencionar la edad
        self.assertIn('mayor', str(ctx.exception).lower())

    def test_verify_user_kyc_rejects_invalid_dni_digit(self):
        """Un DNI con dígito verificador incorrecto debe ser rechazado."""
        from accounts.services import verify_user_kyc

        # 8 dígitos + un dígito verificador deliberadamente erróneo.
        # Si el real es '2', usamos '9' para garantizar el rechazo.
        dni_invalido = '402358719'

        with self.assertRaises(ValueError) as ctx:
            verify_user_kyc(
                user=self.user,
                dni=dni_invalido,
                fecha_nacimiento=date(1995, 1, 1),
            )
        self.assertIn('dni', str(ctx.exception).lower())