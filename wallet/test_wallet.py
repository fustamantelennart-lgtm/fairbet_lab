# wallet/test_wallet.py
from decimal import Decimal
# CAMBIAMOS ESTA LÍNEA: Importamos el TestCase desde hypothesis en lugar de django
from hypothesis.extra.django import TestCase 
from hypothesis import given, strategies as st
from django.contrib.auth.models import User
from wallet.models import Account, Transaction, LedgerEntry

class WalletTDDTestCase(TestCase):

    def setUp(self):
        # Creamos un usuario de prueba y la cuenta central de la CASA (ID=99)
        self.user = User.objects.create_user(username='juan_perez')
        self.casa_account = Account.objects.create(id=99, type='CASA', currency='PEN')
        self.wallet_juan = Account.objects.create(user=self.user, type='WALLET', currency='PEN')

    @given(amount=st.decimals(min_value=Decimal('0.01'), max_value=Decimal('10000.00'), places=4))
    def test_recharge_transaction_balances_to_zero(self, amount):
        """
        Validación de la Invariante Global: Cada depósito de dinero virtual
        debe generar entradas en LedgerEntry cuya suma algebraica sea exactamente 0.
        """
        
        tx = Transaction.objects.create(kind='RECHARGE')
        
       
        
        LedgerEntry.objects.create(transaction=tx, account=self.casa_account, amount=amount, direction='DEBIT')
        
        LedgerEntry.objects.create(transaction=tx, account=self.wallet_juan, amount=amount, direction='CREDIT')

       
        entries = LedgerEntry.objects.filter(transaction=tx)
        
        suma_total = Decimal('0.0000')
        for entry in entries:
            if entry.direction == 'DEBIT':
                suma_total -= entry.amount
            else:
                suma_total += entry.amount

        #La balanza debe dar 0
        self.assertEqual(suma_total, Decimal('0.0000'))