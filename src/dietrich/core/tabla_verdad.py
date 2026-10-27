"""Tabla de verdad en Markdown de cada decisión compuesta (`dietrich mcdc`, QoL #250).

Por cada decisión con dos o más condiciones atómicas se listan las combinaciones que C distingue:
las que difieren solo en condiciones que el cortocircuito no evalúa se juntan en una fila (con «—»
en esas condiciones). En cada fila se marca qué condiciones **deciden** el resultado (cambiarla,
con las demás iguales, cambia la decisión), cuáles están **enmascaradas** (se evalúan pero no
cambian nada en esa fila) y si la fila es parte del conjunto mínimo de vectores MC/DC. Una
condición que no decide en ninguna fila es **redundante**: la decisión no depende de ella.
"""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from dietrich.core.boolean_expr import (
    MAX_CONDICIONES,
    condiciones_evaluadas,
    construir_expresion,
    evaluar,
    seleccion_minima,
    todos_los_pares,
)
from dietrich.core.condition_extractor import DECISION_NODES, get_c_parser

# Más filas que esto no se leen: se muestran solo las del conjunto MC/DC.
MAX_FILAS = 64


class FilaVerdad(BaseModel):
    valores: List[Optional[bool]]  # None: C no evalúa esa condición en esta fila
    resultado: bool
    deciden: List[str] = Field(default_factory=list)
    enmascaradas: List[str] = Field(default_factory=list)
    mcdc_para: List[str] = Field(default_factory=list)  # condiciones cuyo par MC/DC usa esta fila


class TablaDecision(BaseModel):
    linea: int
    condicion: str
    atomos: List[Tuple[str, str]]  # (A, "x > 0")
    filas: List[FilaVerdad] = Field(default_factory=list)
    redundantes: List[str] = Field(default_factory=list)
    filas_omitidas: int = 0


def _tabla(linea: int, texto: str, expresion, atomos: List[str]) -> TablaDecision:
    ids = [chr(ord("A") + i) for i in range(len(atomos))]
    k = len(atomos)
    seleccion = seleccion_minima(todos_los_pares(expresion, k))
    usos: Dict[Tuple[bool, ...], List[str]] = {}
    for i, par in seleccion.items():
        for combo in par or ():
            usos.setdefault(combo, []).append(ids[i])

    filas: Dict[Tuple[Optional[bool], ...], FilaVerdad] = {}
    evaluadas_por_fila: Dict[Tuple[Optional[bool], ...], List[int]] = {}
    deciden_por_fila: Dict[Tuple[Optional[bool], ...], set] = {}
    for combo in product([False, True], repeat=k):
        evaluadas = condiciones_evaluadas(expresion, combo)
        clave = tuple(combo[i] if i in evaluadas else None for i in range(k))
        resultado = evaluar(expresion, combo)
        fila = filas.setdefault(clave, FilaVerdad(valores=list(clave), resultado=resultado))
        evaluadas_por_fila[clave] = sorted(evaluadas)
        # Una fila junta combinaciones que difieren en condiciones no evaluadas: una condición decide
        # si cambiarla cambia el resultado con ALGÚN valor de esas otras.
        deciden_por_fila.setdefault(clave, set()).update(
            i for i in evaluadas if evaluar(expresion, combo[:i] + (not combo[i],) + combo[i + 1:]) != resultado)
        for etiqueta in usos.get(combo, []):
            if etiqueta not in fila.mcdc_para:
                fila.mcdc_para.append(etiqueta)
    deciden_alguna_vez = set()
    for clave, fila in filas.items():
        fila.deciden = [ids[i] for i in sorted(deciden_por_fila[clave])]
        fila.enmascaradas = [ids[i] for i in evaluadas_por_fila[clave] if i not in deciden_por_fila[clave]]
        deciden_alguna_vez.update(fila.deciden)
    # Orden de lectura: como una tabla de verdad, F antes que V y «—» al final de cada columna.
    ordenadas = sorted(filas.values(), key=lambda f: [2 if v is None else int(v) for v in f.valores])
    omitidas = 0
    if len(ordenadas) > MAX_FILAS:
        con_mcdc = [f for f in ordenadas if f.mcdc_para]
        omitidas = len(ordenadas) - len(con_mcdc)
        ordenadas = con_mcdc
    for f in ordenadas:
        f.mcdc_para.sort()
    return TablaDecision(linea=linea, condicion=texto, atomos=list(zip(ids, atomos, strict=True)), filas=ordenadas,
                         redundantes=[i for i in ids if i not in deciden_alguna_vez], filas_omitidas=omitidas)


def tablas_de_verdad(fuente: Path) -> List[TablaDecision]:
    arbol = get_c_parser().parse(fuente.read_bytes())
    tablas: List[TablaDecision] = []

    def recorrer(nodo) -> None:
        if nodo.type in DECISION_NODES:
            condicion = nodo.child_by_field_name("condition")
            if condicion is not None:
                expresion, atomos = construir_expresion(condicion)
                if expresion is not None and 2 <= len(atomos) <= MAX_CONDICIONES:
                    texto = (condicion.text or b"").decode("utf-8", errors="replace").strip()
                    if texto.startswith("(") and texto.endswith(")"):
                        texto = texto[1:-1].strip()
                    tablas.append(_tabla(nodo.start_point.row + 1, texto, expresion, atomos))
        for hijo in nodo.children:
            recorrer(hijo)

    recorrer(arbol.root_node)
    return tablas


def _celda(texto: str) -> str:
    return texto.replace("|", "&#124;")


def markdown(fuente: Path, tablas: List[TablaDecision]) -> str:
    lineas = [f"# Tablas de verdad MC/DC — `{fuente.name}`", ""]
    if not tablas:
        lineas.append("No hay decisiones compuestas (con `&&` o `||`): no hay nada que combinar.")
        return "\n".join(lineas) + "\n"
    lineas += ["V/F: valor de la condición; —: C no la evalúa en ese caso (cortocircuito), su valor no importa.",
               "**Deciden**: cambiarla, con las demás iguales, cambia el resultado. **Enmascaradas**: se evalúan",
               "pero no cambian nada en esa fila. **MC/DC**: la fila es parte del conjunto mínimo de casos.", ""]
    for t in tablas:
        lineas += [f"## Línea {t.linea}: `{_celda(t.condicion)}`", ""]
        cabecera = [f"{i} `{_celda(a)}`" for i, a in t.atomos]
        lineas.append("| # | " + " | ".join(cabecera) + " | Resultado | Deciden | Enmascaradas | MC/DC |")
        lineas.append("| :-: | " + " | ".join(":-:" for _ in cabecera) + " | :-: | :-: | :-: | :-: |")
        for n, f in enumerate(t.filas, 1):
            valores = ["—" if v is None else ("V" if v else "F") for v in f.valores]
            mcdc = f"✓ ({', '.join(f.mcdc_para)})" if f.mcdc_para else ""
            lineas.append(f"| {n} | " + " | ".join(valores) + f" | **{'V' if f.resultado else 'F'}** | "
                          f"{', '.join(f.deciden) or '—'} | {', '.join(f.enmascaradas) or '—'} | {mcdc} |")
        lineas.append("")
        if t.filas_omitidas:
            lineas += [f"> Se omitieron {t.filas_omitidas} filas que no forman parte del conjunto MC/DC.", ""]
        if t.redundantes:
            nombres = ", ".join(f"{i} (`{_celda(a)}`)" for i, a in t.atomos if i in t.redundantes)
            lineas += [f"> [!WARNING]\n> **Condición redundante:** {nombres} no decide el resultado en ninguna "
                       "combinación: la decisión no depende de ella. Sobra o la condición está mal escrita.", ""]
        enmascaradas = sorted({e for f in t.filas for e in f.enmascaradas} - set(t.redundantes))
        if enmascaradas:
            lineas += [f"> Enmascaradas en alguna fila: {', '.join(enmascaradas)}. Para probarlas hacen falta "
                       "las filas en las que sí deciden (las marcadas MC/DC).", ""]
    return "\n".join(lineas)
