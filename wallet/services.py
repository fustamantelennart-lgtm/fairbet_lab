# wallet/services.py
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from django.contrib.auth.models import User
from wallet.models import Account, Transaction, LedgerEntry

def execute_recharge(user: User, amount: Decimal) -> Transaction:
    if amount <= 0:
        raise ValueError("El monto de la recarga debe ser mayor a cero.")

    with transaction.atomic():
        casa_account = Account.objects.get(type=Account.AccountType.CASA)
        user_wallet = Account.objects.get(user=user, type=Account.AccountType.WALLET)

        tx = Transaction.objects.create(kind=Transaction.TransactionKind.RECHARGE)

        LedgerEntry.objects.create(
            transaction=tx, account=casa_account, amount=amount, direction=LedgerEntry.Direction.DEBIT
        )
        LedgerEntry.objects.create(
            transaction=tx, account=user_wallet, amount=amount, direction=LedgerEntry.Direction.CREDIT
        )
        return tx


def execute_bet_lock(user: User, amount: Decimal) -> Transaction:
    """
    Fase GREEN: Bloquea fondos para una apuesta de forma atómica y concurrente.
    Mueve saldos de WALLET del usuario a la cuenta transitoria PENDING.
    """
    if amount <= 0:
        raise ValueError("El monto de la apuesta debe ser mayor a cero.")

    with transaction.atomic():
        # Bloqueo pesimista de concurrencia select_for_update()
        user_wallet = Account.objects.select_for_update().get(user=user, type=Account.AccountType.WALLET)
        pending_account = Account.objects.get(type=Account.AccountType.PENDING)

        # Cálculo dinámico del saldo derivado en tiempo real
        balances = LedgerEntry.objects.filter(account=user_wallet).aggregate(
            credits=Sum('amount', filter=Q(direction=LedgerEntry.Direction.CREDIT)),
            debits=Sum('amount', filter=Q(direction=LedgerEntry.Direction.DEBIT))
        )
        
        credits = balances['credits'] or Decimal('0.0000')
        debits = balances['debits'] or Decimal('0.0000')
        current_balance = credits - debits

        # Control de saldo negativo (Invariante)
        if current_balance < amount:
            raise ValueError(f"Saldo insuficiente para colocar la apuesta. Disponible: {current_balance}")

        # Creación de la transacción con tu enumerado BET_LOCK
        tx = Transaction.objects.create(kind=Transaction.TransactionKind.BET_LOCK)

        # Débito (-) a la billetera del usuario
        LedgerEntry.objects.create(
            transaction=tx, account=user_wallet, amount=amount, direction=LedgerEntry.Direction.DEBIT
        )

        # Crédito (+) a la cuenta transitoria PENDING
        LedgerEntry.objects.create(
            transaction=tx, account=pending_account, amount=amount, direction=LedgerEntry.Direction.CREDIT
        )

        return tx