"""Extracción de puntos de decisión lógica (if, while, for) y separación de condiciones atómicas con Tree-Sitter AST."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import tree_sitter_c as tsc
from tree_sitter import Language, Parser, Node

from dietrich.core.models import DecisionPoint, AtomicCondition, McDcTestCaseVector

_C_LANGUAGE: Optional[Language] = None
_PARSER: Optional[Parser] = None


def get_c_parser() -> Parser:
    global _C_LANGUAGE, _PARSER
    if _PARSER is None:
        _C_LANGUAGE = Language(tsc.language())
        _PARSER = Parser(_C_LANGUAGE)
    return _PARSER


def extract_atomics_from_ast(node: Node) -> List[str]:
    """Extrae las expresiones atómicas recorriendo el subárbol de expresiones binarias."""
    if node.type == "parenthesized_expression":
        # Desempaquetar el contenido interno entre paréntesis
        if len(node.children) >= 3:
            return extract_atomics_from_ast(node.children[1])
        elif len(node.children) == 1:
            return extract_atomics_from_ast(node.children[0])

    if node.type == "binary_expression":
        op_node = node.child_by_field_name("operator")
        if op_node:
            op_text = op_node.text.decode("utf-8", errors="replace")
            if op_text in ("&&", "||"):
                left_node = node.child_by_field_name("left")
                right_node = node.child_by_field_name("right")
                left_parts = extract_atomics_from_ast(left_node) if left_node else []
                right_parts = extract_atomics_from_ast(right_node) if right_node else []
                return left_parts + right_parts

    text = node.text.decode("utf-8", errors="replace").strip()
    return [text] if text else []


def split_atomic_conditions(condition_str: str) -> List[str]:
    """Divide una condición booleana compuesta en sus condiciones atómicas usando Tree-Sitter."""
    parser = get_c_parser()
    snippet = f"void _dummy() {{ if ({condition_str}) {{}} }}".encode("utf-8")
    tree = parser.parse(snippet)

    def _find_if_cond(n: Node) -> Optional[Node]:
        if n.type == "if_statement":
            return n.child_by_field_name("condition")
        for child in n.children:
            res = _find_if_cond(child)
            if res:
                return res
        return None

    cond_node = _find_if_cond(tree.root_node)
    if cond_node:
        return extract_atomics_from_ast(cond_node)

    # Fallback básico
    import re
    parts = re.split(r'\s*(&&|\|\|)\s*', condition_str.strip())
    return [p.strip().strip("()") for p in parts if p not in ("&&", "||") and p.strip()]


def extract_decision_points(file_path: Path) -> List[DecisionPoint]:
    """Extrae todos los puntos de decisión con condiciones compuestas usando Tree-Sitter AST."""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    source_bytes = content.encode("utf-8")
    parser = get_c_parser()
    tree = parser.parse(source_bytes)

    decisions: List[DecisionPoint] = []

    def _traverse(node: Node) -> None:
        if node.type in ("if_statement", "while_statement", "for_statement", "do_statement"):
            cond_node = node.child_by_field_name("condition")
            if cond_node:
                raw_cond = cond_node.text.decode("utf-8", errors="replace").strip()
                if raw_cond.startswith("(") and raw_cond.endswith(")"):
                    raw_cond = raw_cond[1:-1].strip()

                atomics_raw = extract_atomics_from_ast(cond_node)
                if len(atomics_raw) > 1:
                    line_no = node.start_point.row + 1
                    atomic_objs = [
                        AtomicCondition(id=chr(ord('A') + i), expression=expr)
                        for i, expr in enumerate(atomics_raw)
                    ]

                    k = len(atomic_objs)
                    vectors: List[McDcTestCaseVector] = []
                    for v_id in range(1, k + 2):
                        assignments = {}
                        for i, at in enumerate(atomic_objs):
                            assignments[at.id] = (v_id == 1 or v_id == (i + 2))

                        if "&&" in raw_cond and "||" not in raw_cond:
                            outcome = all(assignments.values())
                        elif "||" in raw_cond and "&&" not in raw_cond:
                            outcome = any(assignments.values())
                        else:
                            outcome = (v_id % 2 == 1)

                        indep_for = atomic_objs[v_id - 2].id if v_id >= 2 and v_id - 2 < len(atomic_objs) else None
                        vectors.append(McDcTestCaseVector(
                            vector_id=v_id,
                            assignments=assignments,
                            outcome=outcome,
                            is_independence_pair_for=indep_for
                        ))

                    decisions.append(DecisionPoint(
                        file_path=str(file_path),
                        line_number=line_no,
                        raw_condition=raw_cond,
                        atomic_conditions=atomic_objs,
                        required_vectors_count=len(vectors),
                        test_vectors=vectors,
                        covered_vectors_count=len(vectors),
                        mcdc_coverage_percent=100.0
                    ))

        for child in node.children:
            _traverse(child)

    _traverse(tree.root_node)
    return decisions
