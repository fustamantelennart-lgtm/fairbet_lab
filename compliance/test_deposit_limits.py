# compliance/test_deposit_limits.py
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User


class DepositLimitModelTDDTestCase(TestCase):
    """
    Fase RED — Modelo DepositLimit y su lógica de cooldown asimétrico.

    Reglas de la guía:
      - Bajar el límite es instantáneo.
      - Subir el límite requiere cooldown de 24h.
    """

    def setUp(self):
        self.user, _ = User.objects.get_or_create(username='depositante_test')

    def test_set_daily_limit_initial_is_instantaneous(self):
        """
        Establecer un límite cuando NO había límite previo se aplica de inmediato.
        (Va de None a un valor concreto → se considera 'bajar' protección, instantáneo.)
        """
        from compliance.models import DepositLimit
        from compliance.services import set_daily_deposit_limit

        limit = set_daily_deposit_limit(user=self.user, amount=Decimal('500.0000'))

        self.assertEqual(limit.effective_daily_limit, Decimal('500.0000'))
        self.assertIsNone(limit.pending_daily)

    def test_lowering_daily_limit_is_instantaneous(self):
        """Bajar un límite existente es instantáneo, sin pending."""
        from compliance.services import set_daily_deposit_limit

        # Empezamos con 500
        set_daily_deposit_limit(user=self.user, amount=Decimal('500.0000'))

        # Bajamos a 100
        limit = set_daily_deposit_limit(user=self.user, amount=Decimal('100.0000'))

        self.assertEqual(limit.effective_daily_limit, Decimal('100.0000'))
        self.assertIsNone(limit.pending_daily)

    def test_raising_daily_limit_creates_pending_and_keeps_old_effective(self):
        """Subir un límite NO es instantáneo: queda pending, el efectivo sigue siendo el viejo."""
        from compliance.services import set_daily_deposit_limit

        # Empezamos con 100
        set_daily_deposit_limit(user=self.user, amount=Decimal('100.0000'))

        # Intentamos subir a 500
        limit = set_daily_deposit_limit(user=self.user, amount=Decimal('500.0000'))

        # El efectivo sigue siendo 100 (no se aplicó la subida)
        self.assertEqual(limit.effective_daily_limit, Decimal('100.0000'))
        # Pero queda un pending de 500
        self.assertEqual(limit.pending_daily, Decimal('500.0000'))
        self.assertIsNotNone(limit.pending_daily_at)

    def test_pending_raise_is_promoted_after_24h(self):
        """
        Si el pending tiene más de 24h, el efectivo pasa a ser el nuevo automáticamente.
        Simulamos retrocediendo el pending_daily_at directamente en la DB.
        """
        from compliance.models import DepositLimit
        from compliance.services import set_daily_deposit_limit

        # Setup: límite 100, luego subida pendiente a 500
        set_daily_deposit_limit(user=self.user, amount=Decimal('100.0000'))
        set_daily_deposit_limit(user=self.user, amount=Decimal('500.0000'))

        # Forzamos el pending a haber sido pedido hace 25 horas
        limit = DepositLimit.objects.get(user=self.user)
        limit.pending_daily_at = timezone.now() - timedelta(hours=25)
        limit.save(update_fields=['pending_daily_at'])

        # Al consultar el efectivo, debe promover el pending
        limit.refresh_from_db()
        self.assertEqual(limit.effective_daily_limit, Decimal('500.0000'))
        # Y el pending debe haberse limpiado tras la promoción
        limit.refresh_from_db()
        self.assertIsNone(limit.pending_daily)
        self.assertIsNone(limit.pending_daily_at)


class RechargeBlocksOverDailyLimitTDDTestCase(TestCase):
    """
    Fase RED — Integración: execute_recharge debe rechazar si excede el límite diario.

    La validación cuenta recargas en ventana móvil de 24h.
    """

    def setUp(self):
        from wallet.models import Account
        self.user, _ = User.objects.get_or_create(username='deposit_limited')

        self.wallet, _ = Account.objects.get_or_create(
            user=self.user, type=Account.AccountType.WALLET, currency='PEN'
        )
        Account.objects.get_or_create(type=Account.AccountType.CASA, currency='PEN')

    def test_recharge_within_daily_limit_succeeds(self):
        """Una recarga dentro del límite diario debe permitirse."""
        from wallet.services import execute_recharge
        from compliance.services import set_daily_deposit_limit

        set_daily_deposit_limit(user=self.user, amount=Decimal('100.0000'))

        # Recarga de 50 dentro del límite de 100
        tx = execute_recharge(user=self.user, amount=Decimal('50.0000'))
        self.assertIsNotNone(tx.id)

    def test_recharge_exceeding_daily_limit_raises(self):
        """Una recarga que excede el límite diario debe ser rechazada."""
        from wallet.services import execute_recharge
        from compliance.services import set_daily_deposit_limit

        set_daily_deposit_limit(user=self.user, amount=Decimal('100.0000'))

        # Primera recarga de 80: OK
        execute_recharge(user=self.user, amount=Decimal('80.0000'))

        # Segunda recarga de 50: total sería 130 > 100 → debe rechazar
        with self.assertRaises(ValueError) as ctx:
            execute_recharge(user=self.user, amount=Decimal('50.0000'))

        # El mensaje debe mencionar el límite
        msg = str(ctx.exception).lower()
        self.assertTrue('límite' in msg or 'limite' in msg or 'limit' in msg)