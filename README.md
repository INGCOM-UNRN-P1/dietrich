# DIETRICH — Validador de Cobertura Lógica Avanzada MC/DC en C

**DIETRICH** analiza las decisiones booleanas compuestas (`if (A && (B || C))`) en código fuente C, desglosa las condiciones atómicas y genera la tabla de verdad y los vectores de prueba mínimos ($k + 1$) requeridos para garantizar **Modified Condition/Decision Coverage (MC/DC)** al 100%.

---

## 🎯 Alcance

### Qué cubre
- Medición y verificación estática y dinámica de cobertura lógica avanzada MC/DC (Modified Condition/Decision Coverage) en C.
- Identificación de puntos de decisión condicional (`if`, `while`, operadores `&&`, `||`, ternarios `?:`).
- Demostración de pares de prueba independientes que demuestran que cada condición elemental afecta el resultado de la decisión.
- Reporte de cobertura MC/DC con porcentaje y pares faltantes.

### Qué no cubre (Límites y Delegación)
- Mutation testing de mutantes sintéticos (delegado a `vassili`).
- Generación masiva de datos aleatorios (delegado a `tyrell`).
- Cobertura básica de líneas / bloques gcov (delegado a GCC/gcov).

---

## 📋 Requisitos

### Requisitos de Sistema y Entorno
- Linux / WSL / POSIX. Python >= 3.10.

### Dependencias Externas y Binarios
- `gcc` (para compilación instrumentada).

### Integración en el Ecosistema
- CLI `dietrich`. Plugin en `ripley.plugins` (`mcdc_coverage`).

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
