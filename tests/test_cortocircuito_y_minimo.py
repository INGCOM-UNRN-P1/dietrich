"""Cortocircuito de && y || (QoL #245), cota N + 1 (#247) y alerta con más de 4 condiciones (#250)."""

from pathlib import Path

from dietrich.core.boolean_expr import Atomo, Conjuncion, Disyuncion, condiciones_evaluadas
from dietrich.core.condition_extractor import extract_decision_points

A, B, C = Atomo(0), Atomo(1), Atomo(2)


def test_condiciones_evaluadas():
    y = Conjuncion(A, Conjuncion(B, C))
    assert condiciones_evaluadas(y, (False, True, True)) == {0}
    assert condiciones_evaluadas(y, (True, False, True)) == {0, 1}
    o = Disyuncion(A, B)
    assert condiciones_evaluadas(o, (True, False)) == {0}
    assert condiciones_evaluadas(o, (False, False)) == {0, 1}


def _decisiones(tmp_path: Path, codigo: str):
    f = tmp_path / "f.c"
    f.write_text(codigo, encoding="utf-8")
    return extract_decision_points(f)


def test_minimo_teorico_en_cadenas(tmp_path):
    (y, o) = _decisiones(tmp_path, "int f(int a,int b,int c,int d){\n if (a && b && c) return 1;\n"
                                   " while (a || b || c || d) a--;\n return 0;\n}\n")
    assert (y.required_vectors_count, y.minimum_vectors) == (4, 4)
    assert (o.required_vectors_count, o.minimum_vectors) == (5, 5)
    primero = next(v for v in y.test_vectors if not v.assignments["A"])
    assert primero.not_evaluated == ["B", "C"]


def test_alerta_con_mas_de_cuatro(tmp_path):
    (cuatro, cinco) = _decisiones(tmp_path, "int f(int a,int b,int c,int d,int e){\n if (a && b && c && d) return 1;\n"
                                            " if (a || b || c || d || e) return 2;\n return 0;\n}\n")
    assert cuatro.warning is None
    assert "5 condiciones" in cinco.warning and "6 casos" in cinco.warning
