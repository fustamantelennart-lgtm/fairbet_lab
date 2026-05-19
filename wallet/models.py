from django.db import models
from django.contrib.auth.models import User

class Account(models.Model):
    # Refactor: Convertido a TextChoices para tipado seguro
    class AccountType(models.TextChoices):
        CASA = 'CASA', 'Cuenta Central de la Casa'
        WALLET = 'WALLET', 'Billetera de Saldo Disponible'
        PENDING = 'PENDING', 'Bolsa de Apuestas Pendientes'
        BONUS = 'BONUS', 'Billetera de Bonos'
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='accounts')
    type = models.CharField(max_length=10, choices=AccountType.choices)
    currency = models.CharField(max_length=3, default='PEN')

    def __str__(self):
        return f"Account {self.id} - {self.type}"


class Transaction(models.Model):
    # Refactor: Convertido a TextChoices para tipado seguro
    class TransactionKind(models.TextChoices):
        RECHARGE = 'RECHARGE', 'Deposito de Dinero Virtual'
        BET_LOCK = 'BET_LOCK', 'Bloqueo por Apuesta Activa'
        SETTLEMENT = 'SETTLEMENT', 'Cierre de Apuesta'
    
    kind = models.CharField(max_length=15, choices=TransactionKind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tx {self.id} [{self.kind}]"


class LedgerEntry(models.Model):
    # Refactor: Convertido a TextChoices para tipado seguro
    class Direction(models.TextChoices):
        DEBIT = 'DEBIT', 'Debit (-)'
        CREDIT = 'CREDIT', 'Credit (+)'
    
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='entries')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='entries')
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    direction = models.CharField(max_length=6, choices=Direction.choices)

    def __str__(self):
        return f"Entry {self.id} | {self.direction} | {self.amount}"