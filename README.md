# DIETRICH — Validador de Cobertura Lógica Avanzada MC/DC en C

**DIETRICH** analiza las decisiones booleanas compuestas (`if (A && (B || C))`) en código fuente C, desglosa las condiciones atómicas y genera la tabla de verdad y los vectores de prueba mínimos ($k + 1$) requeridos para garantizar **Modified Condition/Decision Coverage (MC/DC)** al 100%.

---

## 🚀 Uso Rápido

```bash
# Analizar puntos de decisión MC/DC en un archivo C
dietrich analyze algoritmo_logica.c

# Exigir porcentaje mínimo de cobertura
dietrich analyze algoritmo_logica.c --min-coverage 90

# Salida estructurada JSON
dietrich analyze algoritmo_logica.c --json
```

---

## 🔬 Concepto MC/DC

Para una decisión lógica con $k$ condiciones atómicas:
- Una tabla de verdad exhaustiva requiere $2^k$ combinaciones.
- **MC/DC** reduce la suite a $k + 1$ vectores de prueba demostrando que cada condición atómica altera de forma independiente el resultado final de la decisión manteniendo las demás constantes.
