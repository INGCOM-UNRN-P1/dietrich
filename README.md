# DIETRICH — Validador de Cobertura Lógica Avanzada MC/DC en C

> 📖 **Manual de Usuario:** Para una guía exhaustiva de comandos, banderas, arquitectura y ejemplos, consultá el [Manual de Uso](MANUAL.md).

**DIETRICH** analiza las decisiones booleanas compuestas (`if (A && (B || C))`) en código fuente C, desglosa las condiciones atómicas y genera la tabla de verdad y los vectores de prueba mínimos ($k + 1$) requeridos para garantizar **Modified Condition/Decision Coverage (MC/DC)** al 100%.

---

## 🎯 Alcance

### Qué cubre
- Análisis **estático** (tree-sitter) de la cobertura lógica MC/DC (Modified Condition/Decision Coverage) que una decisión C admite: no ejecuta el programa ni mide qué vectores corre tu suite.
- Identificación de puntos de decisión condicional (`if`, `while`, operadores `&&`, `||`, ternarios `?:`).
- Demostración de pares de prueba independientes que demuestran que cada condición elemental afecta el resultado de la decisión.
- Reporte con el porcentaje de condiciones que tienen par de independencia de causa única y la lista de las que no (`missing_independence_pairs`).
- Cobertura **medida** de líneas, ramas y condiciones (`dietrich lines`, con gcc y gcov): el paso previo a MC/DC. Compila con `--coverage`, ejecuta tus pruebas y dice qué líneas no ejecutó ninguna, qué decisiones tomaron un solo camino, qué condición nunca fue verdadera o falsa (gcc 14 o posterior) y qué funciones nunca se llamaron.

### Qué no cubre (Límites y Delegación)
- Mutation testing de mutantes sintéticos (delegado a `vassili`).
- Generación masiva de datos aleatorios (delegado a `tyrell`).
- Medir MC/DC de causa única sobre la ejecución: `dietrich check` es estático y `dietrich lines` mide el MC/DC con enmascaramiento de gcc (`-fcondition-coverage`), que es menos estricto.
- Juzgar si los resultados son correctos: la cobertura dice qué se ejecutó; las aserciones de las pruebas dicen si está bien.

---

## 📋 Requisitos

### Requisitos de Sistema y Entorno
- Linux / WSL / POSIX. Python >= 3.10.

### Dependencias Externas y Binarios
- `check`/`analyze`/`report`: ninguno; el motor es estático y no compila ni ejecuta el código analizado.
- `lines`: `gcc` y su `gcov` (gcc 10 o posterior; con gcc 14 o posterior también mide condiciones). En macOS, el gcc de Homebrew: `--gcc gcc-14 --gcov gcov-14`.

### Integración en el Ecosistema
- CLI `dietrich`. Plugin en `ripley.plugins` (`mcdc_coverage`).

---

## 🚀 Uso Rápido

```bash
# Analizar puntos de decisión MC/DC en un archivo C
dietrich analyze algoritmo_logica.c

# Exigir un porcentaje mínimo de condiciones con par de independencia (por defecto 100; exit 1 si no se alcanza)
dietrich analyze algoritmo_logica.c --min-coverage 90

# Salida estructurada JSON
dietrich analyze algoritmo_logica.c --json

# Cobertura medida de tus pruebas: compila lista.c con test_lista.c, ejecuta y reporta lista.c
dietrich lines lista.c test_lista.c
```

---

## 🔬 Concepto MC/DC

Para una decisión lógica con $k$ condiciones atómicas:
- Una tabla de verdad exhaustiva requiere $2^k$ combinaciones.
- **MC/DC** reduce la suite a $k + 1$ vectores de prueba demostrando que cada condición atómica altera de forma independiente el resultado final de la decisión manteniendo las demás constantes.

Lo que informa `dietrich check` de cada decisión:

- los vectores elegidos reusando los de otras condiciones, y la cota mínima teórica
  (`minimum_vectors`, $k + 1$): en las cadenas de `&&` y de `||` se alcanza;
- en cada vector, las condiciones que C **no evalúa** por el cortocircuito (`not_evaluated`, y `—`
  en la tabla): con `a > 0 && b > 0`, si `a > 0` es falsa, `b > 0` no se evalúa y su valor no importa;
- un aviso (`warning`) cuando la decisión combina más de 4 condiciones: conviene extraer parte en
  una función con nombre o en variables booleanas intermedias.

<!-- p1:referencia:inicio — generado por p1-tools/scripts/readme_generado.py: no editar a mano -->

## Referencia rápida

### Requisitos

- Python ≥ 3.11 y [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Programas del sistema: `gcc`.

| Sistema | `gcc` |
|:--|:--|
| Debian / Ubuntu | `sudo apt install gcc` |
| Fedora | `sudo dnf install gcc` |
| Windows | incluido en el entorno de la cátedra (MSYS2 UCRT64) |
| macOS | `xcode-select --install` (clang como `gcc`) |

### Comandos

| Comando | Descripción |
|:--|:--|
| `dietrich check`, `dietrich analyze` | Analiza condiciones booleanas compuestas (&&, \|\|) y calcula los vectores de prueba requeridos para MC/DC. |
| `dietrich lines` | Mide qué líneas, ramas y condiciones ejecutan tus pruebas (gcc + gcov): el paso previo a MC/DC. |
| `dietrich report` | Genera directamente la sección de reporte Markdown de DIETRICH para Dredd. |
| `dietrich doctor` | Verifica el estado del entorno de análisis MC/DC de DIETRICH. |
| `dietrich version` | Muestra la versión de DIETRICH. |

Ayuda de cada comando: `dietrich <comando> -h`.

### Salida JSON

Con `--json`, estos comandos emiten el resultado como JSON por la salida estándar, para usarlo desde scripts, ripley o dredd: `dietrich check`, `dietrich analyze`, `dietrich lines`, `dietrich doctor`. El de `doctor --json` lleva `schema_version` y `ok`.

### Códigos de salida

| Código | Significado |
|:--|:--|
| `0` | Terminó bien (en `doctor`: está todo lo requerido). |
| `1` | El comando encontró problemas (hallazgos, pruebas que fallan, un umbral que no se alcanza) o un dato no se pudo usar (un archivo ilegible, un formato inválido). |
| `2` | Error de uso: comando, opción o argumento inválido. |

<!-- p1:referencia:fin -->
