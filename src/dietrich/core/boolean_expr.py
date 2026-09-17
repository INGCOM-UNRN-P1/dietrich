"""Árbol de expresión booleana y cálculo de pares de independencia MC/DC.

El criterio implementado es **MC/DC de causa única** (unique-cause): una
condición atómica está cubierta cuando existen dos vectores de prueba que
difieren *solo* en esa condición y producen resultados distintos en la
decisión completa. Es el criterio exigido por DO-178C nivel A y el que se
enseña en la cátedra.

Las condiciones atómicas idénticas (misma expresión textual) se tratan como
una sola condición: `a > 0 && (b || a > 0)` tiene dos condiciones, no tres.
Esto hace que las condiciones acopladas —para las que no existe par de causa
única— aparezcan como pares faltantes en vez de inventar cobertura.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, List, Optional, Sequence, Tuple, Union

from tree_sitter import Node

# Tope de condiciones por decisión para la enumeración exhaustiva (2^k * k).
# Una decisión con más de 16 condiciones atómicas es, en sí misma, un problema
# de legibilidad mucho antes que uno de cobertura.
MAX_CONDICIONES = 16


@dataclass(frozen=True)
class Atomo:
    """Hoja: una condición booleana opaca (`x > 0`, `!flag`, `es_valido(p)`)."""
    indice: int


@dataclass(frozen=True)
class Conjuncion:
    izquierda: "Expr"
    derecha: "Expr"


@dataclass(frozen=True)
class Disyuncion:
    izquierda: "Expr"
    derecha: "Expr"


Expr = Union[Atomo, Conjuncion, Disyuncion]


def construir_expresion(node: Node) -> Tuple[Optional[Expr], List[str]]:
    """Traduce el AST de una condición C a un árbol booleano.

    Devuelve (expresión, textos_de_las_condiciones_atómicas). Las atómicas se
    deduplican por texto, preservando el orden de aparición.
    """
    textos: List[str] = []
    indices: Dict[str, int] = {}

    def _indice_de(texto: str) -> int:
        if texto not in indices:
            indices[texto] = len(textos)
            textos.append(texto)
        return indices[texto]

    def _construir(n: Node) -> Optional[Expr]:
        if n.type == "parenthesized_expression":
            internos = [c for c in n.children if c.type not in ("(", ")")]
            return _construir(internos[0]) if internos else None

        if n.type == "binary_expression":
            op_node = n.child_by_field_name("operator")
            operador = op_node.text.decode("utf-8", errors="replace") if op_node else ""
            if operador in ("&&", "||"):
                izq_node = n.child_by_field_name("left")
                der_node = n.child_by_field_name("right")
                izq = _construir(izq_node) if izq_node else None
                der = _construir(der_node) if der_node else None
                if izq is None or der is None:
                    return izq or der
                return Conjuncion(izq, der) if operador == "&&" else Disyuncion(izq, der)

        texto = n.text.decode("utf-8", errors="replace").strip()
        if not texto:
            return None
        return Atomo(_indice_de(texto))

    expresion = _construir(node)
    return expresion, textos


def evaluar(expr: Expr, valores: Sequence[bool]) -> bool:
    """Evalúa la expresión bajo una asignación de valores por condición."""
    if isinstance(expr, Atomo):
        return valores[expr.indice]
    if isinstance(expr, Conjuncion):
        return evaluar(expr.izquierda, valores) and evaluar(expr.derecha, valores)
    return evaluar(expr.izquierda, valores) or evaluar(expr.derecha, valores)


def pares_de_independencia(
    expr: Expr, cantidad: int
) -> Dict[int, Optional[Tuple[Tuple[bool, ...], Tuple[bool, ...]]]]:
    """Busca, para cada condición, un par de vectores que demuestre su independencia.

    Devuelve {índice_de_condición: (vector_falso, vector_verdadero)} o None
    cuando no existe ningún par de causa única (condición enmascarada o
    acoplada), que es justamente lo que hay que reportar como faltante.
    """
    if cantidad > MAX_CONDICIONES:
        return {i: None for i in range(cantidad)}

    combinaciones = list(product([False, True], repeat=cantidad))
    resultados = {c: evaluar(expr, c) for c in combinaciones}

    pares: Dict[int, Optional[Tuple[Tuple[bool, ...], Tuple[bool, ...]]]] = {}
    for i in range(cantidad):
        encontrado = None
        for combo in combinaciones:
            if combo[i]:
                continue  # se recorre solo desde el lado falso para no duplicar el par
            alterno = list(combo)
            alterno[i] = True
            alterno_t = tuple(alterno)
            if resultados[combo] != resultados[alterno_t]:
                encontrado = (combo, alterno_t)
                break
        pares[i] = encontrado
    return pares
