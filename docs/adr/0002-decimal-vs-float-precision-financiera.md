# ADR 0002 — Manejo de Decimales y Precisión Financiera

**Fecha:** 19/05/2026
**Autor:** [TU NOMBRE]
**Estado:** Aceptado

## Contexto

El reto prohíbe explícitamente el uso de `float` para montos. Necesitamos un tipo numérico exacto para representar fichas virtuales, cuotas (odds) y resultados de multiplicación (payouts) sin errores de redondeo.

## Opciones consideradas

### Opción A: `float` (descartada de inmediato)
- **Pros:** Rendimiento mayor; sintaxis Python directa.
- **Contras:** Errores de representación binaria (`0.1 + 0.2 != 0.3`); el reto lo prohíbe explícitamente; rompe property-based tests.

### Opción B: `Decimal` con `max_digits=18, decimal_places=4`
- **Pros:** Aritmética exacta; cumple el requisito del reto; precisión suficiente para fichas y odds; cuantización explícita evita ambigüedad en redondeo.
- **Contras:** Sintaxis algo más verbosa; multiplicaciones requieren cuantización explícita para no acumular dígitos.

## Decisión

Adoptamos **Opción B**. Todos los `DecimalField` del proyecto usan `max_digits=18, decimal_places=4`. Cualquier resultado de multiplicación (típicamente `payout = stake × odds`) se cuantiza con `.quantize(Decimal('0.0001'))` antes de persistirse.

## Consecuencias

- **Más fácil:** garantizar la invariante "el payout de una apuesta ganadora siempre es stake × odds con precisión exacta".
- **Más difícil:** todo cálculo aritmético debe ser consciente de la cuantización; mezclar `Decimal` con `int`/`float` requiere conversión explícita.
- **Deuda asumida:** las odds usan `decimal_places=2` (formato europeo estándar como `2.50`) pero los amounts usan `decimal_places=4`. La operación `amount * odds` produce un resultado de hasta 6 decimales que cuantizamos a 4. Documentado y testeado.