# wallet/services.py
from decimal import Decimal
from django.db import transaction
from django.contrib.auth.models import User
from wallet.models import Account, Transaction, LedgerEntry

def execute_recharge(user: User, amount: Decimal) -> Transaction:
    """
    Fase GREEN: Ejecuta una recarga de saldo virtual de forma atómica.
    Debita de la cuenta central de la CASA y acredita en la WALLET del usuario.
    """
    if amount <= 0:
        raise ValueError("El monto de la recarga debe ser mayor a cero.")

    # Protegemos la operación con una transacción atómica de base de datos
    with transaction.atomic():
        # 1. Obtener las cuentas necesarias
        casa_account = Account.objects.get(type=Account.AccountType.CASA)
        user_wallet = Account.objects.get(user=user, type=Account.AccountType.WALLET)

        # 2. Registrar la transacción global
        tx = Transaction.objects.create(kind=Transaction.TransactionKind.RECHARGE)

        # 3. Partida Doble: Débito (-) a la Casa
        LedgerEntry.objects.create(
            transaction=tx,
            account=casa_account,
            amount=amount,
            direction=LedgerEntry.Direction.DEBIT
        )

        # 4. Partida Doble: Crédito (+) a la Billetera del Usuario
        LedgerEntry.objects.create(
            transaction=tx,
            account=user_wallet,
            amount=amount,
            direction=LedgerEntry.Direction.CREDIT
        )

        return tx