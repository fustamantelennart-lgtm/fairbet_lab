# events/services.py
"""
Servicios de dominio para el catálogo de eventos y mercados.

Análogo a wallet/services.py: nada de creación parcial. Si se crea
un Market 1X2, sus 3 Selections (LOCAL/DRAW/AWAY) se crean en la
misma transacción atómica. Igual que un LedgerEntry nunca existe
sin su par en partida doble.
"""
from decimal import Decimal
from django.db import transaction

from events.models import Event, Market, Selection


def create_1x2_market(
    event: Event,
    odds_local: Decimal,
    odds_draw: Decimal,
    odds_away: Decimal,
) -> Market:
    """
    Crea un Market 1X2 sobre un Event, con sus 3 Selections, atómicamente.

    Garantiza que el Market nunca exista en un estado inconsistente
    (por ejemplo, creado pero con solo 2 selections).

    Validaciones:
      - Las 3 odds deben ser > 1.00 (en odds decimales, una odd de 1.00
        significa "no hay ganancia"; valores ≤1 son inválidos).
      - El Event no puede estar VOIDED.
    """
    # Validaciones de pre-condición
    for label, odds in (('local', odds_local), ('draw', odds_draw), ('away', odds_away)):
        if odds <= Decimal('1.00'):
            raise ValueError(
                f"La cuota de '{label}' ({odds}) debe ser mayor a 1.00."
            )

    if event.status == Event.EventStatus.VOIDED:
        raise ValueError(
            f"No se pueden crear mercados sobre un Event anulado ({event})."
        )

    with transaction.atomic():
        market = Market.objects.create(
            event=event,
            kind=Market.MarketKind.MARKET_1X2,
        )

        Selection.objects.create(
            market=market,
            code=Selection.SelectionCode.LOCAL,
            odds=odds_local,
        )
        Selection.objects.create(
            market=market,
            code=Selection.SelectionCode.DRAW,
            odds=odds_draw,
        )
        Selection.objects.create(
            market=market,
            code=Selection.SelectionCode.AWAY,
            odds=odds_away,
        )

        return market