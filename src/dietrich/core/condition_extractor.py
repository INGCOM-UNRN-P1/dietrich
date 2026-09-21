"""Extracción de puntos de decisión lógica (if, while, for) y separación de condiciones atómicas con Tree-Sitter AST."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node

from dietrich.core.boolean_expr import (
    construir_expresion,
    evaluar,
    pares_de_independencia,
)
from dietrich.core.models import DecisionPoint, AtomicCondition, McDcTestCaseVector

_C_LANGUAGE: Optional[Language] = None
_PARSER: Optional[Parser] = None


def get_c_parser() -> Parser:
    global _C_LANGUAGE, _PARSER
    if _PARSER is None:
        _C_LANGUAGE = Language(tsc.language())
        _PARSER = Parser(_C_LANGUAGE)
    return _PARSER


# Nodos que introducen una decisión lógica. `conditional_expression` cubre el
# operador ternario `?:`, que el README declara desde el principio.
DECISION_NODES = (
    "if_statement",
    "while_statement",
    "for_statement",
    "do_statement",
    "conditional_expression",
)


def _analizar_decision(file_path: Path, node: Node, cond_node: Node) -> Optional[DecisionPoint]:
    """Construye el punto de decisión evaluando la expresión real, no un patrón sintético."""
    raw_cond = cond_node.text.decode("utf-8", errors="replace").strip()
    if raw_cond.startswith("(") and raw_cond.endswith(")"):
        raw_cond = raw_cond[1:-1].strip()

    expresion, textos = construir_expresion(cond_node)
    if expresion is None or len(textos) < 2:
        return None

    atomic_objs = [
        AtomicCondition(id=chr(ord("A") + i), expression=texto)
        for i, texto in enumerate(textos)
    ]
    pares = pares_de_independencia(expresion, len(textos))

    # Un vector puede demostrar la independencia de varias condiciones a la vez;
    # se emite una sola vez, acumulando las etiquetas que justifica.
    vectores: Dict[Tuple[bool, ...], List[str]] = {}
    faltantes: List[str] = []
    for indice, par in pares.items():
        etiqueta = atomic_objs[indice].id
        if par is None:
            faltantes.append(etiqueta)
            continue
        for combo in par:
            vectores.setdefault(combo, []).append(etiqueta)

    test_vectors: List[McDcTestCaseVector] = []
    for v_id, (combo, etiquetas) in enumerate(sorted(vectores.items()), start=1):
        test_vectors.append(McDcTestCaseVector(
            vector_id=v_id,
            assignments={atomic_objs[i].id: combo[i] for i in range(len(atomic_objs))},
            outcome=evaluar(expresion, combo),
            is_independence_pair_for=",".join(sorted(etiquetas)),
        ))

    cubiertas = len(atomic_objs) - len(faltantes)
    cobertura = (cubiertas / len(atomic_objs) * 100.0) if atomic_objs else 100.0

    return DecisionPoint(
        file_path=str(file_path),
        line_number=node.start_point.row + 1,
        raw_condition=raw_cond,
        atomic_conditions=atomic_objs,
        required_vectors_count=len(test_vectors),
        test_vectors=test_vectors,
        covered_vectors_count=len(test_vectors),
        mcdc_coverage_percent=round(cobertura, 2),
        missing_independence_pairs=sorted(faltantes),
    )


def extract_decision_points(file_path: Path) -> List[DecisionPoint]:
    """Extrae todos los puntos de decisión con condiciones compuestas usando Tree-Sitter AST."""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    source_bytes = content.encode("utf-8")
    parser = get_c_parser()
    tree = parser.parse(source_bytes)

    decisions: List[DecisionPoint] = []

    def _traverse(node: Node) -> None:
        if node.type in DECISION_NODES:
            cond_node = node.child_by_field_name("condition")
            if cond_node:
                decision = _analizar_decision(file_path, node, cond_node)
                if decision:
                    decisions.append(decision)

        for child in node.children:
            _traverse(child)

    _traverse(tree.root_node)
    return decisions
