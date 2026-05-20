## Historial de Consultas

| Fecha       | Fase / Tarea | Propósito de la Consulta | Código / Concepto Afectado |
| :--- | :--- | :--- | :--- |
| 19/05/2026 | Sprint 1: Diseño | Explicación conceptual del sistema de partida doble para el Wallet e invariantes financieras. | Diseño del modelo de datos (`Account`, `Transaction`, `LedgerEntry`) reflejado en bocetos a mano. |

| 19/05/2026 | Sprint 1: TDD / DB | Corrección del TestCase heredado para compatibilidad de Hypothesis con transacciones de PostgreSQL. | Archivo `wallet/test_wallet.py` corregido y pasando. |

| 19/05/2026 | Sprint 1: Lógica / Servicios | Implementación del servicio `execute_recharge` bajo TDD y corrección de colisión de IDs (id=99 manual) en el `setUp` para compatibilidad con Hypothesis. | Archivo `wallet/services.py` creado y suite pasando en verde. |

| 19/05/2026 | Sprint 1: Lógica de Apuestas | Creación del modelo `Bet` con máquina de estados (`ACCEPTED`, `WON`, `LOST`) y propiedad `potential_payout` usando  `Decimal`. Enlace estricto a transacciones. | Migraciones aplicadas y suite de pruebas incrementada a 5 passed exitosos. |

| 19/05/2026 | Sprint 1: Liquidación de Apuestas | Diseño contable de la liquidación (3 entries para WON: PENDING+CASA→WALLET; 2 entries para LOST: PENDING→CASA). Implementación de `execute_bet_settlement` con `select_for_update` sobre la `Bet` para prevenir doble pago concurrente. Pruebas property-based con Hypothesis. | `wallet/services.py` (función `execute_bet_settlement`) y nueva clase `BetSettlementTDDTestCase` en `wallet/test_wallet.py`. |



| 19/05/2026  | Sprint 2 - Ciclo TDD 6 (catálogo eventos)  | Diseño de máquina de estados del Event, separación entre Market/Selection y discusión del cálculo del margen del operador en odds decimales (`sum(1/odds) - 1`). | `events/models.py` (Event, Market, Selection); `events/services.py::create_1x2_market`. |

| 19/05/2026  | Sprint 2 - Ciclo TDD 7 (KYC DNI peruano)   | Verificación del algoritmo oficial del dígito verificador (Módulo 11, pesos [3,2,7,6,5,4,3,2]) citando fuentes públicas (Excel Negocios, El Comercio). Diseño del flujo de validación KYC + mayoría de edad + estado por defecto PENDING_VERIFICATION. | `accounts/dni.py`, `accounts/models.py::UserProfile`, `accounts/services.py::verify_user_kyc`. |

| 19/05/2026  | Sprint 2 - Ciclo TDD 8a (autoexclusión)    | Diseño del modelo SelfExclusion con TextChoices (TEMPORARY_7/30/90/INDEFINITE), discusión sobre por qué NO exponer revoke al usuario (decisión psicológica), e integración bloqueante con execute_bet_lock vía import local para evitar ciclos. | `compliance/models.py`, `compliance/services.py`, edit en `wallet/services.py::execute_bet_lock`. |

| 19/05/2026  | Sprint 2 - Ciclo TDD 8b (límites depósito) | Diseño del cooldown asimétrico 24h (subir/bajar), discusión sobre ventana móvil vs calendario (decisión: móvil, estándar regulatorio), implementación de promoción automática del pending al consultar `effective_*_limit`. | `compliance/models.py::DepositLimit`, `compliance/services.py` (set_*_deposit_limit + check_deposit_within_limits), edit en `wallet/services.py::execute_recharge`. |
| 19/05/2026  | Sprint 2 - Depuración                      | Diagnóstico de IndentationError en `execute_recharge` por paste manual con indentación corrupta (comentario en col 0, import en col 5).                                              | `wallet/services.py::execute_recharge`. |