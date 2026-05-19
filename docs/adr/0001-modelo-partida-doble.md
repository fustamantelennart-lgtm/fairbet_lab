# ADR 0001 — Modelo de Partida Doble para el Wallet

**Fecha:** 19/05/2026
**Autor:** [TU NOMBRE]
**Estado:** Aceptado

## Contexto

El reto exige integridad financiera total: la suma de débitos y créditos debe ser cero en cada operación, el saldo debe derivarse (nunca almacenarse) y no debe haber forma de generar dinero de la nada. Hay varias formas de modelar movimientos de dinero.

## Opciones consideradas

### Opción A: Una columna `balance` en `Account` y un log de movimientos opcional
- **Pros:** Lecturas instantáneas, modelo simple.
- **Contras:** Permite incoherencias entre saldo y movimientos; un `UPDATE` mal hecho rompe la integridad sin dejar rastro; auditoría débil; cumple peor con el espíritu de la Ley 31557.

### Opción B: Partida doble estricta — `Account`, `Transaction`, `LedgerEntry` con dirección DEBIT/CREDIT
- **Pros:** Imposible introducir dinero "fantasma": toda transacción debe balancearse a cero. Saldo derivado por agregación SQL; trazabilidad completa; auditoría inmutable natural; estándar contable real.
- **Contras:** Lectura de saldo cuesta una agregación (mitigable con índice y caché si fuera necesario). Más tablas que la opción A.

## Decisión

Adoptamos **Opción B**. La integridad financiera es no negociable según el reto (4 puntos directos de la rúbrica). El costo extra de una agregación por consulta de saldo es despreciable frente al riesgo de inconsistencias.

## Consecuencias

- **Más fácil:** demostrar invariantes con property-based testing (suma=0 por transacción, saldo no negativo).
- **Más difícil:** las consultas de saldo requieren agregación; en alta concurrencia hay que combinar con `select_for_update()`.
- **Deuda asumida:** sin caché de saldo, queries de dashboard con muchos usuarios pueden requerir índices compuestos futuros.