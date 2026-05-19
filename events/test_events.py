# events/test_events.py
from decimal import Decimal
from hypothesis.extra.django import TestCase
from hypothesis import given, strategies as st


class EventCatalogTDDTestCase(TestCase):
    """
    Fase RED — Catálogo de eventos y mercados (Nivel 1, punto 3 de la guía).

    Valida:
      - El estado inicial de un Event es SCHEDULED.
      - El estado inicial de un Market es OPEN.
      - El service create_1x2_market crea un Market con exactamente
        3 Selections (LOCAL/DRAW/AWAY) con las odds dadas.
      - El margen del operador de un Market 1X2 es matemáticamente
        consistente (positivo y razonable).
    """

    def _crear_event(self):
        """Helper: crea un evento de prueba en estado SCHEDULED."""
        from events.models import Event
        from datetime import datetime, timezone
        return Event.objects.create(
            home_team='Perú',
            away_team='Brasil',
            start_time=datetime(2026, 6, 14, 20, 0, tzinfo=timezone.utc),
        )

    def test_event_default_status_is_scheduled(self):
        """Un Event recién creado debe estar en SCHEDULED por defecto."""
        from events.models import Event
        event = self._crear_event()
        self.assertEqual(event.status, Event.EventStatus.SCHEDULED)

    def test_market_default_status_is_open(self):
        """Un Market recién creado debe estar en OPEN por defecto."""
        from events.models import Event, Market
        event = self._crear_event()
        market = Market.objects.create(
            event=event,
            kind=Market.MarketKind.MARKET_1X2,
        )
        self.assertEqual(market.status, Market.MarketStatus.OPEN)

    def test_create_1x2_market_service_creates_three_selections(self):
        """
        El service create_1x2_market(event, odds_local, odds_draw, odds_away)
        debe crear un Market 1X2 con exactamente 3 Selections con los
        códigos LOCAL/DRAW/AWAY y las odds correctas.
        """
        from events.services import create_1x2_market
        from events.models import Market, Selection

        event = self._crear_event()

        market = create_1x2_market(
            event=event,
            odds_local=Decimal('3.50'),
            odds_draw=Decimal('3.10'),
            odds_away=Decimal('1.80'),
        )

        # 1. Es un Market 1X2
        self.assertEqual(market.kind, Market.MarketKind.MARKET_1X2)

        # 2. Tiene exactamente 3 selections
        selections = market.selections.all()
        self.assertEqual(selections.count(), 3)

        # 3. Los códigos son exactamente LOCAL, DRAW, AWAY
        codes = set(selections.values_list('code', flat=True))
        self.assertEqual(
            codes,
            {Selection.SelectionCode.LOCAL,
             Selection.SelectionCode.DRAW,
             Selection.SelectionCode.AWAY}
        )

        # 4. Las odds asignadas son las correctas
        self.assertEqual(
            selections.get(code=Selection.SelectionCode.LOCAL).odds,
            Decimal('3.50')
        )
        self.assertEqual(
            selections.get(code=Selection.SelectionCode.DRAW).odds,
            Decimal('3.10')
        )
        self.assertEqual(
            selections.get(code=Selection.SelectionCode.AWAY).odds,
            Decimal('1.80')
        )

    @given(
        odds_local=st.decimals(min_value=Decimal('1.10'), max_value=Decimal('10.00'), places=2),
        odds_draw=st.decimals(min_value=Decimal('1.10'), max_value=Decimal('10.00'), places=2),
        odds_away=st.decimals(min_value=Decimal('1.10'), max_value=Decimal('10.00'), places=2),
    )
    def test_operator_margin_is_mathematically_consistent(
        self, odds_local, odds_draw, odds_away
    ):
        """
        Property-based test: para cualquier triplete de odds en rango realista,
        el margen del operador calculado como sum(1/odds) - 1 debe poder
        computarse sin errores y dar un Decimal finito.

        Esta es la invariante mínima del mercado 1X2. El nivel de margen
        exacto (5%, 8%, 12%) es decisión del operador y se valida en
        tests de configuración, no aquí.
        """
        from events.services import create_1x2_market
        event = self._crear_event()

        market = create_1x2_market(
            event=event,
            odds_local=odds_local,
            odds_draw=odds_draw,
            odds_away=odds_away,
        )

        # El método market.operator_margin debe existir y retornar un Decimal
        margin = market.operator_margin
        self.assertIsInstance(margin, Decimal)
        # El margen puede ser negativo (favorece al apostador) o positivo (favorece a la casa).
        # Lo que NO puede pasar: no estar acotado.
        self.assertTrue(Decimal('-1.0') < margin < Decimal('5.0'))