## Historial de Consultas

| Fecha       | Fase / Tarea | Propósito de la Consulta | Código / Concepto Afectado |
| :--- | :--- | :--- | :--- |
| 19/05/2026 | Sprint 1: Diseño | Explicación conceptual del sistema de partida doble para el Wallet e invariantes financieras. | Diseño del modelo de datos (`Account`, `Transaction`, `LedgerEntry`) reflejado en bocetos a mano. |

| 19/05/2026 | Sprint 1: TDD / DB | Corrección del TestCase heredado para compatibilidad de Hypothesis con transacciones de PostgreSQL. | Archivo `wallet/test_wallet.py` corregido y pasando. |

| 19/05/2026 | Sprint 1: Lógica / Servicios | Implementación del servicio `execute_recharge` bajo TDD y corrección de colisión de IDs (id=99 manual) en el `setUp` para compatibilidad con Hypothesis. | Archivo `wallet/services.py` creado y suite pasando en verde. |

| 19/05/2026 | Sprint 1: Lógica de Apuestas | Creación del modelo `Bet` con máquina de estados (`ACCEPTED`, `WON`, `LOST`) y propiedad `potential_payout` usando  `Decimal`. Enlace estricto a transacciones. | Migraciones aplicadas y suite de pruebas incrementada a 5 passed exitosos. |

| 19/05/2026 | Sprint 1: Liquidación de Apuestas | Diseño contable de la liquidación (3 entries para WON: PENDING+CASA→WALLET; 2 entries para LOST: PENDING→CASA). Implementación de `execute_bet_settlement` con `select_for_update` sobre la `Bet` para prevenir doble pago concurrente. Pruebas property-based con Hypothesis. | `wallet/services.py` (función `execute_bet_settlement`) y nueva clase `BetSettlementTDDTestCase` en `wallet/test_wallet.py`. |