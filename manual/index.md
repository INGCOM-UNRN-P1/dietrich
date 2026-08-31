---
title: "Manual de Referencia: dietrich"
subtitle: "Dietrich — Validador de Cobertura Lógica MC/DC (Modified Condition/Decision Coverage) en C"
author: "Cátedra de Algoritmos y Programación"
date: "2026-08-31"
---

(manual-dietrich)=
# Dietrich — Validador de Cobertura Lógica MC/DC (Modified Condition/Decision Coverage) en C

````{abstract}
**Rol en el ecosistema:** Análisis formal de cobertura lógica sobre condiciones booleanas complejas en estructuras de control (if, while), asegurando que cada condición atómica afecte independientemente el resultado.
````

---

(manual-dietrich-proposito)=
## 1. Propósito y Filosofía Pedagógica

La herramienta **`dietrich`** forma parte del ecosistema oficial de software de la cátedra. Su diseño sigue principios pedagógicos rigurosos:

1. **Evidencia Técnica Directa**: Todo diagnóstico se fundamenta en la norma ISO C (C11/C23), en el modelo de memoria del sistema o en convenciones arquitectónicas formales.
2. **Acción Correctiva Concreta**: Cada advertencia incluye la prescripción técnica inmediata para resolver el defecto sin recurrir a conjeturas.
3. **Autonomía del Estudiante**: Facilita la autoevaluación local antes de la entrega final del trabajo práctico.
4. **Objetividad Docente**: Estandariza la corrección automática eliminando discrepancias subjetivas en la evaluación.

---

(manual-dietrich-instalacion)=
## 2. Instalación y Diagnóstico del Entorno

````{important}
Asegurate de contar con el compilador GCC/Clang y las librerías del sistema instaladas antes de ejecutar `dietrich`.
````

Para comprobar el estado de salud de tu entorno de trabajo y las dependencias auxiliares:

````{code-block} bash
# Comprobación de dependencias del sistema
dietrich doctor
````

Si se detecta la falta de alguna utilidad (como `gdb`, `valgrind`, `clang-format` o `typst`), el comando indicará el paquete exacto a instalar según tu distribución GNU/Linux o entorno MSYS2.

---

(manual-dietrich-comandos)=
## 3. Referencia Completa de Comandos CLI

A continuación se detallan los subcomandos principales disponibles en `dietrich`:

| Sintaxis del Comando | Descripción y Efecto |
| :--- | :--- |
| `dietrich analyze src/auth.c` | Calcula la matriz de cobertura MC/DC sobre todas las decisiones lógicas. |
| `dietrich report --md reporte_mcdc.md src/` | Genera el informe de pares de prueba faltantes en Markdown. |
| `dietrich test-matrix src/controlador.c` | Imprime la tabla de verdad y combinaciones evaluadas. |
| `dietrich doctor` | Verifica la integración con gcov y llvm-cov. |

````{tip}
Podés agregar el flag `--json` a la mayoría de los comandos para exportar resultados en formato estructurado o `--md` para generar reportes Markdown para el informe de entrega.
````

---

(manual-dietrich-tutorial)=
## 4. Tutorial Paso a Paso con Ejemplos Reales

### Caso de Estudio

Considerá el siguiente fragmento de código representativo:

````{code-block} c
:linenos:
#include <stdbool.h>

// Decisión booleana compuesta con 3 condiciones atómicas: (A && B) || C
bool autorizar_acceso(bool es_admin, bool tiene_token, bool modo_emergencia) {
    if ((es_admin && tiene_token) || modo_emergencia) {
        return true;
    }
    return false;
}
````

### Ejecución de la Herramienta

Ejecutá el análisis desde tu terminal:

````{code-block} bash
dietrich analyze src/auth.c
````

### Salida Obtenida en Consola

````{code-block} text
Decisión: ((es_admin && tiene_token) || modo_emergencia) en auth.c:5
┌─────────────────────────┬──────────────┬──────────────┬──────────────────┐
│ Condición Atómica       │ True Outcome │ False Outcome│ MC/DC Satisfecho │
├─────────────────────────┼──────────────┼──────────────┼──────────────────┤
│ A (es_admin)            │ Testcase #1  │ Testcase #2  │ ✓ SÍ             │
│ B (tiene_token)         │ Testcase #1  │ Testcase #3  │ ✓ SÍ             │
│ C (modo_emergencia)     │ Testcase #4  │ Testcase #5  │ ✓ SÍ             │
└─────────────────────────┴──────────────┴──────────────┴──────────────────┘
[✓] Cobertura MC/DC: 100% (4 pares de prueba independientes cubiertos).
````

````{note}
Prestá atención a la explicación pedagógica generada: la herramienta no solo señala la línea del problema, sino que explica la causa raíz y el impacto en memoria o arquitectura.
````

---

(manual-dietrich-ejercicios)=
## 5. Ejercicios Prácticos y Desafíos

Practicá el uso avanzado de **`dietrich`** resolviendo los siguientes ejercicios:

````{exercise} Desafío 1: Auditoría de Validador de Acceso
Evaluar si la suite de tests actual cubre todas las ramas atómicas de `autorizar_acceso()`.

**Instrucción de ejecución:**
```bash
dietrich analyze src/auth.c
```
````

````{solution} Desafío 1
```bash
dietrich analyze src/auth.c
# Verificá que la operación concluya exitosamente con código de salida 0.
```
````

````{exercise} Desafío 2: Generación de Pares de Prueba Faltantes
Obtener los casos de prueba requeridos para satisfacer 100% MC/DC en un clasificador.

**Instrucción de ejecución:**
```bash
dietrich test-matrix src/clasificador.c
```
````

````{solution} Desafío 2
```bash
dietrich test-matrix src/clasificador.c
# Revisá el archivo generado o el informe en terminal para confirmar la resolución del problema.
```
````

````{exercise} Desafío 3: Informe para Certificación Docente
Exportar el informe Markdown de cobertura lógica de la entrega.

**Instrucción de ejecución:**
```bash
dietrich report --md reporte_mcdc.md src/
```
````

````{solution} Desafío 3
```bash
dietrich report --md reporte_mcdc.md src/
# Comprobá que la salida confirme la ausencia de advertencias o errores pendientes.
```
````

---

(manual-dietrich-makefile)=
## 6. Integración en el Flujo de Trabajo y Makefile

Para incorporar `dietrich` de forma automática a tu flujo de desarrollo, agregá la siguiente regla en el `Makefile` de tu proyecto:

````{code-block} makefile
check-dietrich:
	@echo "=== Ejecutando verificación con dietrich ==="
	dietrich check src/ include/

.PHONY: check-dietrich
````

Ejecutá `make check-dietrich` antes de cada commit para asegurar que tu código conserve el estado de aprobación.
