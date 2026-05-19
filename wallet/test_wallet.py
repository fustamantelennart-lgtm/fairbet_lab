# wallet/test_wallet.py
from decimal import Decimal
from hypothesis.extra.django import TestCase 
from hypothesis import given, strategies as st
from django.contrib.auth.models import User
from wallet.models import Account, Transaction, LedgerEntry

class WalletTDDTestCase(TestCase):

    def setUp(self):
        # Solución: Quitamos el id=99 manual para que la base de datos use su autoincremental limpio
        self.user, _ = User.objects.get_or_create(username='juan_perez')
        self.casa_account, _ = Account.objects.get_or_create(type=Account.AccountType.CASA, currency='PEN')
        self.wallet_juan, _ = Account.objects.get_or_create(user=self.user, type=Account.AccountType.WALLET, currency='PEN')

    @given(amount=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('10000.00'), places=4))
    def test_recharge_transaction_balances_to_zero(self, amount):
        """
        Validación de la Invariante Global: Cada depósito de dinero virtual
        debe generar entradas en LedgerEntry cuya suma algebraica sea exactamente 0.
        """
        tx = Transaction.objects.create(kind=Transaction.TransactionKind.RECHARGE)
        
        LedgerEntry.objects.create(transaction=tx, account=self.casa_account, amount=amount, direction=LedgerEntry.Direction.DEBIT)
        LedgerEntry.objects.create(transaction=tx, account=self.wallet_juan, amount=amount, direction=LedgerEntry.Direction.CREDIT)

        entries = LedgerEntry.objects.filter(transaction=tx)
        
        suma_total = Decimal('0.0000')
        for entry in entries:
            if entry.direction == LedgerEntry.Direction.DEBIT:
                suma_total -= entry.amount
            else:
                suma_total += entry.amount

        # La balanza debe dar 0
        self.assertEqual(suma_total, Decimal('0.0000'))

    @given(amount=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('10000.00'), places=4))
    def test_service_execute_recharge_creates_balanced_ledger_entries(self, amount):
        """
        Fase GREEN: Probar que el servicio de recarga automatizado crea 
        una transacción y dos asientos contables asociados que balancean a cero.
        """
        service_user, _ = User.objects.get_or_create(username='tester_wallet_service')
        
        casa = Account.objects.get(type=Account.AccountType.CASA)
        user_wallet, _ = Account.objects.get_or_create(user=service_user, type=Account.AccountType.WALLET, currency='PEN')

        # 2. Ejecución (Act)
        from wallet.services import execute_recharge
        
        transaction = execute_recharge(user=service_user, amount=amount)

        # 3. Verificación (Assert)
        self.assertIsNotNone(transaction.id)
        self.assertEqual(transaction.kind, Transaction.TransactionKind.RECHARGE)

        entries = transaction.entries.all()
        self.assertEqual(entries.count(), 2)

        total_balance = Decimal('0.0000')
        for entry in entries:
            if entry.direction == LedgerEntry.Direction.DEBIT:
                total_balance -= entry.amount
            elif entry.direction == LedgerEntry.Direction.CREDIT:
                total_balance += entry.amount

        self.assertEqual(total_balance, Decimal('0.0000'))

    @given(amount=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('500.00'), places=4))
    def test_service_bet_lock_transfers_funds_to_pending_account(self, amount):
        """
        Fase RED: Probar que el bloqueo de fondos para una apuesta descuenta
        de la WALLET del usuario y acumula en APUESTAS_PENDIENTES.
        """
        # 1. Configuración del escenario
        bet_user, _ = User.objects.get_or_create(username='apostador_tdd')
        
        # Creamos las cuentas requeridas por la guía
        user_wallet, _ = Account.objects.get_or_create(user=bet_user, type=Account.AccountType.WALLET, currency='PEN')
        pending_account, _ = Account.objects.get_or_create(type=Account.AccountType.APUESTAS_PENDIENTES, currency='PEN')
        casa_account, _ = Account.objects.get_or_create(type=Account.AccountType.CASA, currency='PEN')

        # Simulamos que el usuario tiene saldo inicial dándole un crédito previo desde la CASA
        init_tx = Transaction.objects.create(kind=Transaction.TransactionKind.RECHARGE)
        LedgerEntry.objects.create(transaction=init_tx, account=casa_account, amount=amount, direction=LedgerEntry.Direction.DEBIT)
        LedgerEntry.objects.create(transaction=init_tx, account=user_wallet, amount=amount, direction=LedgerEntry.Direction.CREDIT)

        # 2. Ejecución (Act)
        from wallet.services import execute_bet_lock
        
        transaction = execute_bet_lock(user=bet_user, amount=amount)

        # 3. Verificación (Assert)
        self.assertIsNotNone(transaction.id)
        
        # Verificamos que se crearon los dos asientos balanceados a cero
        entries = transaction.entries.all()
        self.assertEqual(entries.count(), 2)
        
        # Comprobamos que el dinero llegó a Apuestas Pendientes
        pending_entry = entries.get(account=pending_account)
        self.assertEqual(pending_entry.direction, LedgerEntry.Direction.CREDIT)
        self.assertEqual(pending_entry.amount, amount)

    @given(amount=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('500.00'), places=4))
    def test_service_bet_lock_insufficient_funds_raises_error(self, amount):
        """
        Fase RED (Invariante): Validar que si el usuario intenta apostar un monto
        mayor a su saldo disponible, el sistema bloquee la operación arrojando ValueError.
        """
        poor_user, _ = User.objects.get_or_create(username='apostador_pobre')
        Account.objects.get_or_create(user=poor_user, type=Account.AccountType.WALLET, currency='PEN')
        Account.objects.get_or_create(type=Account.AccountType.APUESTAS_PENDIENTES, currency='PEN')

        from wallet.services import execute_bet_lock

        # Intentar bloquear fondos sin saldo debe lanzar un ValueError contable obligatoriamente
        with self.assertRaises(ValueError):
            execute_bet_lock(user=poor_user, amount=amount)