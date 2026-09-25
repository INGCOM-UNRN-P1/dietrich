# Manual de Uso y Referencia Técnica: dietrich

> **DIETRICH** — Validador de cobertura lógica avanzada MC/DC (Modified Condition/Decision Coverage) en C
> **Versión:** `0.1.0` · **CLI principal:** `dietrich` · **Plugin Ripley:** `mcdc_coverage`

---

## 1. Arquitectura y Propósito Pedagógico

`dietrich` forma parte del ecosistema de herramientas de la cátedra de Programación 1 (UNRN). Su objetivo central es resolver de forma modular, determinista y automatizada las tareas asociadas a su dominio específico dentro del ciclo de desarrollo, evaluación y aprendizaje de software en C.

### Alcance Funcional (Qué cubre)
- Análisis **estático** (tree-sitter) de la cobertura lógica MC/DC (Modified Condition/Decision Coverage) que una decisión C admite: no ejecuta el programa ni mide qué vectores corre tu suite.
- Identificación de puntos de decisión condicional (`if`, `while`, operadores `&&`, `||`, ternarios `?:`).
- Demostración de pares de prueba independientes que demuestran que cada condición elemental afecta el resultado de la decisión.
- Reporte con el porcentaje de condiciones que tienen par de independencia de causa única y la lista de las que no (`missing_independence_pairs`).

### Límites de Responsabilidad y Delegación (Qué no cubre)
- Mutation testing de mutantes sintéticos (delegado a `vassili`).
- Generación masiva de datos aleatorios (delegado a `tyrell`).
- Cobertura básica de líneas / bloques gcov (delegado a GCC/gcov).
- Medición dinámica de qué vectores ejecuta una suite (no se ejecuta el binario).

### Principios de Diseño
- **Enfoque Pedagógico:** Diagnósticos y mensajes en español rioplatense orientados a facilitar la comprensión de errores conceptuales.
- **Salida Estructurada Dual:** Soporte nativo para visualización enriquecida en terminal (Rich) y salida parseable para orquestadores (`--json`).
- **Integración Contractual:** Capacidad de emitir secciones de reporte para `dredd` (`dredd-section`) y actuar como satélite orquestado por `ripley`.
- **Idempotencia y Robustez:** Validación de precondiciones y comandos de autodiagnóstico (`doctor`) para verificación del entorno.

---

## 2. Instalación y Requisitos

### Requisitos del Sistema
- **Python:** `>= 3.10` (recomendado Python 3.11 o 3.12).
- **Gestor de paquetes:** [`uv`](https://github.com/astral-sh/uv) (entorno estándar de cátedra).
- **Toolchain C (si aplica):** GCC / Clang, Make, GDB y bibliotecas estándar de desarrollo.

### Instalación en el Entorno de Usuario
Para instalar la herramienta de forma global y aislada en el sistema mediante `uv tool`:
```bash
uv tool install --editable /home/mrtin/dev/tools/dietrich
```

### Verificación de Instalación
Ejecutá el comando `doctor` para constatar que todas las dependencias y binarios requeridos estén presentes y operativos:
```bash
dietrich doctor
```

---

## 3. Guía Integral de Comandos (CLI)

| Comando | Descripción Breve |
| :--- | :--- |
| [`dietrich check`](#check) | Analiza condiciones booleanas compuestas (&&, ||) y calcula los vectores de prueba requeridos para MC/DC. |
| [`dietrich analyze`](#analyze) | Analiza condiciones booleanas compuestas (&&, ||) y calcula los vectores de prueba requeridos para MC/DC. |
| [`dietrich report`](#report) | Genera directamente la sección de reporte Markdown de DIETRICH para Dredd. |
| [`dietrich doctor`](#doctor) | Verifica el estado del entorno de análisis MC/DC de DIETRICH. |
| [`dietrich version`](#version) | Muestra la versión de DIETRICH. |

### `dietrich check`

Analiza condiciones booleanas compuestas (&&, ||) y calcula los vectores de prueba requeridos para MC/DC.

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `target_file` | `<class 'pathlib._local.Path'>` | Archivo C a auditar por cobertura MC/DC |

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--min-coverage`, `-m` | `<class 'float'>` | `100.0` | Porcentaje mínimo de condiciones con par de independencia; por debajo, sale con código 1 |
| `--json` | `<class 'bool'>` | `False` | Emitir salida en formato JSON estructurado |
| `--md`, `--output-md` | `Optional[pathlib._local.Path]` | `None` | Generar sección de reporte en formato Markdown para fusión en Dredd. |

#### Ejemplo de Invocación
```bash
dietrich check <target_file>
```

### `dietrich analyze`

Analiza condiciones booleanas compuestas (&&, ||) y calcula los vectores de prueba requeridos para MC/DC.

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `target_file` | `<class 'pathlib._local.Path'>` | Archivo C a auditar por cobertura MC/DC |

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--min-coverage`, `-m` | `<class 'float'>` | `100.0` | Porcentaje mínimo de condiciones con par de independencia; por debajo, sale con código 1 |
| `--json` | `<class 'bool'>` | `False` | Emitir salida en formato JSON estructurado |
| `--md`, `--output-md` | `Optional[pathlib._local.Path]` | `None` | Generar sección de reporte en formato Markdown para fusión en Dredd. |

#### Ejemplo de Invocación
```bash
dietrich analyze <target_file>
```

### `dietrich report`

Genera directamente la sección de reporte Markdown de DIETRICH para Dredd.

#### Argumentos
| Argumento | Tipo | Descripción |
| :--- | :--- | :--- |
| `target_file` | `<class 'pathlib._local.Path'>` | Archivo C a auditar por cobertura MC/DC |

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--output`, `-o` | `Optional[pathlib._local.Path]` | `None` | Ruta de destino del archivo Markdown. |

#### Ejemplo de Invocación
```bash
dietrich report <target_file>
```

### `dietrich doctor`

Verifica el estado del entorno de análisis MC/DC de DIETRICH.

#### Opciones y Banderas
| Opción / Banderas | Tipo | Por Defecto | Descripción |
| :--- | :--- | :--- | :--- |
| `--json` | `<class 'bool'>` | `False` | Emitir diagnóstico en formato JSON estructurado. |

#### Ejemplo de Invocación
```bash
dietrich doctor
```

### `dietrich version`

Muestra la versión de DIETRICH.

#### Ejemplo de Invocación
```bash
dietrich version
```

---

## 4. Formatos de Salida e Integración con el Ecosistema

### Modo Interactivo / Terminal (Rich)
Por defecto, la herramienta renderiza paneles, árboles y tablas estilizadas para facilitar la lectura del estudiante y docente en terminales modernas con soporte ANSI.

### Modo Estructurado JSON (`--json`)
Para integración con pipelines de CI/CD, scripts de automatización u orquestadores externos, la opción `--json` emite un documento JSON estricto por la salida estándar (`stdout`), dirigiendo cualquier mensaje de logging a `stderr`:
```bash
dietrich check --json
```

### Integración con Dredd (`dredd-section`)
Cuando la herramienta genera reportes de evaluación para entregas de alumnos, produce una sección Markdown estandarizada conforme al contrato de integración de Dredd (v1.0.0):
```markdown
<!-- dredd-section: dietrich, tool=dietrich, version=0.1.0, status=ok -->
```
Este encabezado garantiza la agregación determinista de los hallazgos en la rúbrica docente.

### Integración con Ripley
`dietrich` está registrada en el catálogo de plugins satélites de Ripley (`SATELLITE_CATALOG`). Puede invocarse directamente a través del motor de evaluación de Ripley configurando el análisis en `ripley.toml`.

---

## 5. Diagnóstico y Códigos de Salida

### Códigos de Retorno (`exit code`)
| Código | Significado |
| :---: | :--- |
| `0` | Ejecución exitosa sin hallazgos críticos ni errores de sintaxis. |
| `1` | Hallazgos pedagógicos detectados, infracción de reglas o advertencias activas. |
| `2` | Error de sintaxis en argumentos CLI o archivo fuente no encontrado. |
| `>2` | Error no recuperable del sistema, fallo de memoria o excepción interna. |

### Diagnóstico del Entorno (`doctor`)
Ante comportamientos inesperados, verificá el estado operativo con:
```bash
dietrich doctor
```
Comprueba la presencia de las dependencias requeridas y la integridad de los componentes del paquete.