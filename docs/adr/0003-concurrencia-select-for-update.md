# ADR 0003 — Estrategia de Concurrencia: Bloqueo Pesimista

**Fecha:** 19/05/2026
**Autor:** [TU NOMBRE]
**Estado:** Aceptado

## Contexto

El reto exige prevenir el doble gasto: un usuario que envía dos peticiones simultáneas de apuesta no debe poder gastar más de su saldo. Esto se generaliza a toda operación financiera concurrente (recarga, bloqueo de apuesta, liquidación).

## Opciones consideradas

### Opción A: Concurrencia optimista (version columns / `check then write`)
- **Pros:** Mejor throughput en escenarios de baja contención; no bloquea filas.
- **Contras:** Requiere lógica de reintento explícita en el cliente o el servicio; las race conditions detectadas se manifiestan como excepciones que el código tiene que manejar; más complejo de testear correctamente.

### Opción B: Concurrencia pesimista con `select_for_update()` dentro de `transaction.atomic()`
- **Pros:** PostgreSQL bloquea la fila a nivel BD; cualquier petición concurrente espera o falla limpiamente; lógica de servicio simple y lineal; trivial de testear con threads o procesos.
- **Contras:** Posible cuello de botella si muchísimos workers leen el mismo wallet a la vez (no es nuestro caso a esta escala).

## Decisión

Adoptamos **Opción B**. Cada servicio crítico (`execute_recharge`, `execute_bet_lock`, `execute_bet_settlement`) usa `select_for_update()` sobre la entidad cuya consistencia protege (el wallet del usuario para los dos primeros; la propia `Bet` para el settlement), todo dentro de un `transaction.atomic()`.

## Consecuencias

- **Más fácil:** demostrar la invariante "ningún wallet termina con saldo negativo" en property-based tests.
- **Más difícil:** los servicios deben mantener el orden de adquisición de locks consistente entre todas las rutas para evitar deadlocks (por ahora no hay rutas que requieran múltiples locks).
- **Deuda asumida:** si en una versión futura un servicio necesita lockear simultáneamente el wallet de un usuario y la `Bet`, hay que definir un orden de adquisición global (p.ej. siempre wallet antes que bet) y documentarlo aquí.