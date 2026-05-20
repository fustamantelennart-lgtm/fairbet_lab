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
    Bloquea fondos para una apuesta de forma atómica y concurrente.
    Mueve saldos de WALLET del usuario a la cuenta transitoria PENDING.

    Antes de tocar el wallet, valida controles regulatorios:
      - El usuario NO debe estar autoexcluido (Nivel 1 punto 5 - juego responsable).
    """
    if amount <= 0:
        raise ValueError("El monto de la apuesta debe ser mayor a cero.")

    # --- Control regulatorio (juego responsable) ---
    # Import local: evita ciclo de imports wallet <-> compliance.
    from compliance.services import is_user_self_excluded
    if is_user_self_excluded(user):
        raise ValueError(
            f"El usuario {user.username} está autoexcluido. "
            f"No puede colocar apuestas hasta que el periodo de autoexclusión termine."
        )

    with transaction.atomic():
        # Bloqueo pesimista de concurrencia
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

        # Invariante: nunca dejar el wallet en negativo
        if current_balance < amount:
            raise ValueError(f"Saldo insuficiente para colocar la apuesta. Disponible: {current_balance}")

        tx = Transaction.objects.create(kind=Transaction.TransactionKind.BET_LOCK)

        LedgerEntry.objects.create(
            transaction=tx, account=user_wallet, amount=amount, direction=LedgerEntry.Direction.DEBIT
        )
        LedgerEntry.objects.create(
            transaction=tx, account=pending_account, amount=amount, direction=LedgerEntry.Direction.CREDIT
        )

        return tx


def execute_bet_settlement(bet, won: bool) -> Transaction:
    """
    Liquida una apuesta resolviendo la partida doble desde la cuenta PENDING.

    Casos:
      - WON  : libera stake de PENDING, CASA aporta la ganancia, WALLET recibe payout.
                 Asientos: PENDING(D) + CASA(D) -> WALLET(C)   [3 entradas]
      - LOST : libera stake de PENDING hacia CASA.
                 Asientos: PENDING(D) -> CASA(C)               [2 entradas]

    Invariantes que protege:
      - select_for_update sobre la Bet impide doble liquidación concurrente.
      - Validación de estado ACCEPTED impide liquidar bets ya cerradas.
      - Toda la operación es atómica: o cuadra todo, o no queda nada a medias.
      - La suma firmada de entries es cero (partida doble).
    """
    from wallet.models import Bet  # import local para evitar ciclos

    with transaction.atomic():
        # Bloqueo pesimista sobre la bet: previene que dos workers liquiden la misma a la vez.
        bet_locked = Bet.objects.select_for_update().get(pk=bet.pk)

        # Solo apuestas ACEPTADAS pueden liquidarse (idempotencia y prevención de doble pago).
        if bet_locked.status != Bet.BetStatus.ACCEPTED:
            raise ValueError(
                f"La apuesta {bet_locked.pk} no está en estado ACCEPTED "
                f"(estado actual: {bet_locked.status}). No puede liquidarse."
            )

        user_wallet = Account.objects.get(
            user=bet_locked.user, type=Account.AccountType.WALLET
        )
        pending_account = Account.objects.get(type=Account.AccountType.PENDING)
        casa_account = Account.objects.get(type=Account.AccountType.CASA)

        tx = Transaction.objects.create(kind=Transaction.TransactionKind.SETTLEMENT)

        stake = bet_locked.amount

        if won:
            payout = (stake * bet_locked.odds).quantize(Decimal('0.0001'))
            house_loss = (payout - stake).quantize(Decimal('0.0001'))

            LedgerEntry.objects.create(
                transaction=tx, account=pending_account,
                amount=stake, direction=LedgerEntry.Direction.DEBIT,
            )
            LedgerEntry.objects.create(
                transaction=tx, account=casa_account,
                amount=house_loss, direction=LedgerEntry.Direction.DEBIT,
            )
            LedgerEntry.objects.create(
                transaction=tx, account=user_wallet,
                amount=payout, direction=LedgerEntry.Direction.CREDIT,
            )

            bet_locked.status = Bet.BetStatus.WON
        else:
            LedgerEntry.objects.create(
                transaction=tx, account=pending_account,
                amount=stake, direction=LedgerEntry.Direction.DEBIT,
            )
            LedgerEntry.objects.create(
                transaction=tx, account=casa_account,
                amount=stake, direction=LedgerEntry.Direction.CREDIT,
            )

            bet_locked.status = Bet.BetStatus.LOST

        bet_locked.save(update_fields=['status'])
        return tx