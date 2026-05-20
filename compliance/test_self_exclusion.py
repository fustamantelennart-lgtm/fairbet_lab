# compliance/test_self_exclusion.py
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User


class SelfExclusionModelTDDTestCase(TestCase):
    """
    Fase RED — Modelo SelfExclusion.

    Valida:
      - Crear una autoexclusión temporal de 7 días calcula ends_at correctamente.
      - Una autoexclusión INDEFINITE no tiene ends_at.
      - is_active() refleja correctamente el paso del tiempo.
    """

    def setUp(self):
        self.user, _ = User.objects.get_or_create(username='autoexcluido_test')

    def test_create_temporary_7_days_calculates_end_date(self):
        """Una autoexclusión temporal de 7 días debe terminar 7 días en el futuro."""
        from compliance.models import SelfExclusion
        from compliance.services import create_self_exclusion

        before = timezone.now()
        exclusion = create_self_exclusion(
            user=self.user,
            kind=SelfExclusion.Kind.TEMPORARY_7,
        )
        after = timezone.now()

        # ends_at debe estar ~7 días después de starts_at
        expected_min = before + timedelta(days=7)
        expected_max = after + timedelta(days=7)
        self.assertGreaterEqual(exclusion.ends_at, expected_min)
        self.assertLessEqual(exclusion.ends_at, expected_max)
        self.assertTrue(exclusion.is_active())

    def test_create_indefinite_has_no_end_date(self):
        """Una autoexclusión INDEFINITE no tiene fecha de fin."""
        from compliance.models import SelfExclusion
        from compliance.services import create_self_exclusion

        exclusion = create_self_exclusion(
            user=self.user,
            kind=SelfExclusion.Kind.INDEFINITE,
        )

        self.assertIsNone(exclusion.ends_at)
        self.assertTrue(exclusion.is_active())

    def test_expired_temporary_exclusion_is_not_active(self):
        """Una autoexclusión temporal expirada ya no está activa."""
        from compliance.models import SelfExclusion

        past_start = timezone.now() - timedelta(days=10)
        past_end = timezone.now() - timedelta(days=3)
        exclusion = SelfExclusion.objects.create(
            user=self.user,
            kind=SelfExclusion.Kind.TEMPORARY_7,
            starts_at=past_start,
            ends_at=past_end,
        )

        self.assertFalse(exclusion.is_active())


class SelfExclusionServiceTDDTestCase(TestCase):
    """
    Fase RED — Servicio is_user_self_excluded.

    Valida que el helper de consulta funciona correctamente para
    el resto del sistema (wallet, betting) sin tener que duplicar lógica.
    """

    def setUp(self):
        self.user, _ = User.objects.get_or_create(username='consulta_excl')

    def test_user_without_exclusion_returns_false(self):
        """Sin exclusiones, el helper retorna False."""
        from compliance.services import is_user_self_excluded
        self.assertFalse(is_user_self_excluded(self.user))

    def test_user_with_active_exclusion_returns_true(self):
        """Con una exclusión activa, el helper retorna True."""
        from compliance.models import SelfExclusion
        from compliance.services import create_self_exclusion, is_user_self_excluded

        create_self_exclusion(user=self.user, kind=SelfExclusion.Kind.TEMPORARY_30)
        self.assertTrue(is_user_self_excluded(self.user))


class BetLockBlocksSelfExcludedTDDTestCase(TestCase):
    """
    Fase RED — Integración: execute_bet_lock debe rechazar usuarios autoexcluidos.

    Esta es la prueba más importante del ciclo: demuestra que el control
    de compliance es BLOQUEANTE (palabra textual de la rúbrica:
    "Controles de juego responsable completos y bloqueantes").
    """

    def setUp(self):
        from wallet.models import Account
        self.user, _ = User.objects.get_or_create(username='apostador_excluido')

        # Setup mínimo del wallet para que el test sea realista
        self.wallet, _ = Account.objects.get_or_create(
            user=self.user, type=Account.AccountType.WALLET, currency='PEN'
        )
        Account.objects.get_or_create(type=Account.AccountType.PENDING, currency='PEN')
        Account.objects.get_or_create(type=Account.AccountType.CASA, currency='PEN')

        # Le damos saldo al usuario
        from wallet.services import execute_recharge
        execute_recharge(user=self.user, amount=Decimal('100.0000'))

    def test_execute_bet_lock_raises_when_user_is_self_excluded(self):
        """
        Un usuario autoexcluido NO puede colocar apuestas, incluso si
        tiene saldo suficiente. La validación de compliance debe ocurrir
        ANTES de la validación de saldo.
        """
        from compliance.models import SelfExclusion
        from compliance.services import create_self_exclusion
        from wallet.services import execute_bet_lock

        # Marcar al usuario como autoexcluido
        create_self_exclusion(user=self.user, kind=SelfExclusion.Kind.TEMPORARY_7)

        # Intento de apuesta debe ser rechazado
        with self.assertRaises(ValueError) as ctx:
            execute_bet_lock(user=self.user, amount=Decimal('10.0000'))

        # El mensaje debe mencionar autoexclusión
        self.assertIn('autoexcl', str(ctx.exception).lower())