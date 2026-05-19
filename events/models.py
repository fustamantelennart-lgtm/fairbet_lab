# events/models.py
from decimal import Decimal
from django.db import models


class Event(models.Model):
    """
    Un evento deportivo (típicamente un partido).

    Estados (máquina de estados del evento):
      SCHEDULED -> programado, acepta apuestas pre-partido
      LIVE      -> en curso, acepta apuestas in-play (Nivel 2)
      FINISHED  -> terminado, los markets pueden liquidarse
      SUSPENDED -> pausado (corte, retraso); no acepta apuestas hasta reanudar
      VOIDED    -> anulado; todas las apuestas se reembolsan
    """

    class EventStatus(models.TextChoices):
        SCHEDULED = 'SCHEDULED', 'Programado'
        LIVE = 'LIVE', 'En vivo'
        FINISHED = 'FINISHED', 'Finalizado'
        SUSPENDED = 'SUSPENDED', 'Suspendido'
        VOIDED = 'VOIDED', 'Anulado'

    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    status = models.CharField(
        max_length=15,
        choices=EventStatus.choices,
        default=EventStatus.SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} ({self.status})"


class Market(models.Model):
    """
    Una pregunta apostable sobre un Event.

    En Nivel 1 solo soportamos 1X2 (gana local, empate, gana visitante).
    Niveles superiores añadirán OVER_UNDER, BTTS, HANDICAP, etc.

    Estados del market:
      OPEN      -> acepta apuestas
      SUSPENDED -> congelado temporalmente (gol/expulsión en in-play)
      SETTLED   -> liquidado; ya no acepta nuevas apuestas
    """

    class MarketKind(models.TextChoices):
        MARKET_1X2 = '1X2', 'Resultado 1X2'

    class MarketStatus(models.TextChoices):
        OPEN = 'OPEN', 'Abierto a apuestas'
        SUSPENDED = 'SUSPENDED', 'Suspendido temporalmente'
        SETTLED = 'SETTLED', 'Liquidado'

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='markets'
    )
    kind = models.CharField(max_length=20, choices=MarketKind.choices)
    status = models.CharField(
        max_length=15,
        choices=MarketStatus.choices,
        default=MarketStatus.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def operator_margin(self) -> Decimal:
        """
        Calcula el margen del operador para un Market 1X2.

        Fórmula estándar en odds decimales:
            margin = (1/odds_local + 1/odds_draw + 1/odds_away) - 1

        Si margin > 0, la casa tiene ventaja matemática esperada.
        Si margin == 0, el mercado es justo (probabilidades suman 1).
        Si margin < 0, el mercado favorece al apostador (situación rara).

        Retorna Decimal con 4 decimales para consistencia con
        el resto del sistema contable.
        """
        if self.kind != self.MarketKind.MARKET_1X2:
            raise ValueError("operator_margin solo aplica a markets 1X2 por ahora.")

        inv_sum = Decimal('0.0000')
        for sel in self.selections.all():
            inv_sum += Decimal('1') / sel.odds

        return (inv_sum - Decimal('1')).quantize(Decimal('0.0001'))

    def __str__(self):
        return f"Market {self.id} [{self.kind}] for {self.event}"


class Selection(models.Model):
    """
    Una respuesta posible dentro de un Market.

    Para 1X2 son exactamente 3: LOCAL / DRAW / AWAY.
    Para Over/Under serán OVER / UNDER. Etc.

    El campo `won` se llena en la liquidación:
      None  -> aún no liquidado
      True  -> esta selección ganó
      False -> esta selección perdió
    """

    class SelectionCode(models.TextChoices):
        LOCAL = 'LOCAL', 'Gana local'
        DRAW = 'DRAW', 'Empate'
        AWAY = 'AWAY', 'Gana visitante'

    market = models.ForeignKey(
        Market, on_delete=models.CASCADE, related_name='selections'
    )
    code = models.CharField(max_length=10, choices=SelectionCode.choices)
    odds = models.DecimalField(max_digits=6, decimal_places=2)
    won = models.BooleanField(null=True, blank=True, default=None)

    class Meta:
        # Una misma selección (ej. LOCAL) solo puede existir UNA vez por market.
        constraints = [
            models.UniqueConstraint(
                fields=['market', 'code'],
                name='unique_selection_per_market',
            )
        ]

    def __str__(self):
        return f"Sel {self.code} @ {self.odds} (market {self.market_id})"