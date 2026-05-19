from django.db import models
from django.contrib.auth.models import User

class Account(models.Model):
    ACCOUNT_TYPES = [
        ('CASA', 'Cuenta Central de la Casa'),
        ('WALLET', 'Billetera de Saldo Disponible'),
        ('PENDING', 'Bolsa de Apuestas Pendientes'),
        ('BONUS', 'Billetera de Bonos'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='accounts')
    type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    currency = models.CharField(max_length=3, default='PEN')

    def __str__(self):
        return f"Account {self.id} - {self.type}"


class Transaction(models.Model):
    TRANSACTION_KINDS = [
        ('RECHARGE', 'Deposito de Dinero Virtual'),
        ('BET_LOCK', 'Bloqueo por Apuesta Activa'),
        ('SETTLEMENT', 'Cierre de Apuesta'),
    ]
    
    kind = models.CharField(max_length=15, choices=TRANSACTION_KINDS)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tx {self.id} [{self.kind}]"


class LedgerEntry(models.Model):
    DIRECTION_CHOICES = [
        ('DEBIT', 'Debit (-)'),
        ('CREDIT', 'Credit (+)'),
    ]
    
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='entries')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='entries')
    
    # Alta precisión matemática exigida para auditorías financieras
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    direction = models.CharField(max_length=6, choices=DIRECTION_CHOICES)

    def __str__(self):
        return f"Entry {self.id} | {self.direction} | {self.amount}"