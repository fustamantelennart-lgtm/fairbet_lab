# Lecciones Aprendidas — Sprint 1 (Wallet + Apuestas)

## Intento Fallido 1: Conflicto por persistencia de `manage.py` residual
* **Fecha:** 19/05/2026
* **Contexto:** Re-intento de inicialización de Django tras eliminar el directorio `config`.
* **Error presentado:** `CommandError: /app/manage.py already exists. Overlaying a project into an existing directory won't replace conflicting files.`
* **Causa raíz:** El comando anterior generó exitosamente el archivo `manage.py` en la raíz antes de fallar por el conflicto de directorios. Django bloqueó la nueva ejecución al detectar el archivo residual.
* **Solución aplicada:** Remover manualmente el archivo `manage.py` residual de la raíz del espacio de trabajo y ejecutar el comando por segunda vez sobre un directorio completamente limpio.

## Intento Fallido 2: `NameError: name 'Decimal' is not defined` en modelo `Bet`
* **Fecha:** 19/05/2026
* **Contexto:** Ciclo TDD 4 (modelo `Bet`), fase GREEN. Al ejecutar `makemigrations`, Django crasheó antes de procesar la migración.
* **Error presentado:** `NameError: name 'Decimal' is not defined` en `wallet/models.py::Bet.potential_payout`.
* **Causa raíz:** Se usó `Decimal` como type hint en la firma del método (`def potential_payout(self) -> Decimal:`) pero el `import` estaba dentro del método (lazy import), no a nivel de módulo. Python evalúa los type hints al cargar la clase, antes de invocar el método, por lo que el símbolo no estaba disponible.
* **Solución aplicada:** Mover `from decimal import Decimal` al inicio del archivo `wallet/models.py` como import global. Lección: los type hints en firmas requieren imports a nivel de módulo, no locales.

## Intento Fallido 3: Diseño contable incompleto en liquidación WON (2 entries vs 3 entries)
* **Fecha:** 19/05/2026
* **Contexto:** Ciclo TDD 5 (`execute_bet_settlement`), fase RED. La primera versión del test asumía que liquidar una apuesta ganada implicaba solo 2 entries (PENDING → WALLET).
* **Error presentado:** El diseño habría roto la invariante de partida doble: si solo se mueve `payout` desde PENDING al WALLET, PENDING queda con saldo negativo porque solo había `stake` bloqueado, no `payout`.
* **Causa raíz:** Confusión conceptual sobre el flujo de fondos. PENDING solo contiene el `stake` que se bloqueó al ejecutar `execute_bet_lock`; la ganancia neta (`payout - stake`) debe salir de la CASA, que es quien financia las apuestas ganadoras.
* **Solución aplicada:** Reajustar el test antes del GREEN para exigir **3 entries** en WON: PENDING(DEBIT) por stake + CASA(DEBIT) por `house_loss` + WALLET(CREDIT) por payout total. La suma firmada queda en cero y se preserva la integridad contable.

## Intento Fallido 4: Regresión por pérdida accidental del `return tx`
* **Fecha:** 19/05/2026
* **Contexto:** Ciclo TDD 5 (`execute_bet_settlement`), fase GREEN. Al añadir la función nueva al final de `wallet/services.py`, se eliminó por accidente la línea `return tx` de la función previa `execute_bet_lock`.
* **Error presentado:** 5 tests previamente verdes pasaron a rojo. `AttributeError: 'NoneType' object has no attribute 'id'` en el test directo de `execute_bet_lock`, y cascada de `IntegrityError: null value in column "lock_transaction_id"` en todos los tests que dependían del helper `_crear_bet_con_fondos_bloqueados`.
* **Causa raíz:** Edit manual no atómico sobre un archivo crítico. La función seguía creando las entries (efecto colateral en la DB) pero devolvía `None` implícitamente, propagándolo a `Bet.objects.create(lock_transaction=None)` y violando la constraint NOT NULL.
* **Solución aplicada:** Restaurar el `return tx` al final de `execute_bet_lock`. **Valor de TDD demostrado en vivo:** la regresión se detectó inmediatamente (el mismo pytest), se localizó en minutos (5 tests fallando con el mismo síntoma apuntan a la dependencia común), y no llegó a producción. Si esto hubiera ocurrido sin tests, el bug habría sido "las apuestas no se pueden crear" — síntoma vago, debugging horas.