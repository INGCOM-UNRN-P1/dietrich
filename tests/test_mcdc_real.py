"""Regresión de DIETRICH-D0301/D0302/D0303: MC/DC real, no sintético.

Antes el motor fabricaba los vectores con un patrón fijo (`v_id == 1 or
v_id == i+2`), calculaba el resultado con `v_id % 2 == 1` para operadores
mixtos y reportaba 100 % de cobertura literal.
"""

from itertools import product
from pathlib import Path

import pytest

from dietrich.core.boolean_expr import (
    construir_expresion,
    evaluar,
    pares_de_independencia,
)
from dietrich.core.condition_extractor import extract_decision_points, get_c_parser
from dietrich.core.mcdc_analyzer import audit_mcdc_coverage


def _decisiones(tmp_path: Path, cuerpo: str):
    archivo = tmp_path / "caso.c"
    archivo.write_text(cuerpo, encoding="utf-8")
    return extract_decision_points(archivo)


def _expresion(condicion: str):
    parser = get_c_parser()
    arbol = parser.parse(f"int f(void) {{ if ({condicion}) {{}} return 0; }}".encode())

    def buscar(n):
        if n.type == "if_statement":
            return n.child_by_field_name("condition")
        for hijo in n.children:
            encontrado = buscar(hijo)
            if encontrado:
                return encontrado
        return None

    return construir_expresion(buscar(arbol.root_node))


@pytest.mark.parametrize(
    "condicion, referencia",
    [
        ("a && (b || c)", lambda a, b, c: a and (b or c)),
        ("(a || b) && c", lambda a, b, c: (a or b) and c),
        ("a || (b && c)", lambda a, b, c: a or (b and c)),
        ("(a && b) || (b && c)", lambda a, b, c: (a and b) or (b and c)),
    ],
)
def test_outcome_coincide_con_la_semantica_de_c(condicion, referencia):
    """El resultado sale de evaluar el árbol, no de la paridad del id del vector."""
    expresion, textos = _expresion(condicion)
    assert len(textos) == 3
    for valores in product([False, True], repeat=3):
        assert evaluar(expresion, valores) == referencia(*valores), (
            f"{condicion} con {valores}"
        )


def test_caso_exacto_del_hallazgo(tmp_path):
    """`a && (b || c)` con {A:F, B:T, C:F} vale False, no True (DIETRICH-D0301)."""
    expresion, _ = _expresion("a && (b || c)")
    assert evaluar(expresion, (False, True, False)) is False


def test_pares_son_de_causa_unica(tmp_path):
    """Cada par debe diferir en exactamente una condición y cambiar el resultado."""
    expresion, textos = _expresion("a && (b || c)")
    pares = pares_de_independencia(expresion, len(textos))
    for indice, par in pares.items():
        assert par is not None
        falso, verdadero = par
        difieren = [i for i in range(len(textos)) if falso[i] != verdadero[i]]
        assert difieren == [indice], f"el par de {indice} cambia {difieren}"
        assert evaluar(expresion, falso) != evaluar(expresion, verdadero)


def test_condicion_enmascarada_se_reporta_como_par_faltante(tmp_path):
    """En `a && (b || a)`, `b` no puede afectar el resultado de forma independiente."""
    decisiones = _decisiones(tmp_path, "int g(int a,int b){ if (a && (b || a)) return 1; return 0; }")
    assert len(decisiones) == 1
    decision = decisiones[0]
    assert decision.missing_independence_pairs == ["B"]
    assert decision.mcdc_coverage_percent == 50.0


def test_ternario_es_una_decision(tmp_path):
    """DIETRICH-D0302: el README declara `?:` desde siempre."""
    decisiones = _decisiones(tmp_path, "int f(int a,int b){ return (a && b) ? 1 : 0; }")
    assert len(decisiones) == 1
    assert decisiones[0].raw_condition == "a && b"


def test_cobertura_y_veredicto_no_son_decorativos(tmp_path):
    """DIETRICH-D0303: 100 % solo si todas las condiciones tienen par."""
    archivo = tmp_path / "mixto.c"
    archivo.write_text(
        "int f(int a,int b,int c){ if (a && (b || c)) return 1; return 0; }\n"
        "int g(int a,int b){ if (a && (b || a)) return 1; return 0; }\n",
        encoding="utf-8",
    )
    reporte = audit_mcdc_coverage(archivo)
    assert reporte.passed is False
    assert reporte.average_mcdc_coverage < 100.0


def test_decision_totalmente_cubierta_aprueba(tmp_path):
    archivo = tmp_path / "ok.c"
    archivo.write_text("int f(int a,int b){ if (a && b) return 1; return 0; }", encoding="utf-8")
    reporte = audit_mcdc_coverage(archivo)
    assert reporte.passed is True
    assert reporte.average_mcdc_coverage == 100.0


def test_condiciones_repetidas_son_una_sola(tmp_path):
    """`a > 0 && (b || a > 0)` tiene dos condiciones atómicas, no tres."""
    decisiones = _decisiones(
        tmp_path, "int f(int a,int b){ if (a > 0 && (b || a > 0)) return 1; return 0; }"
    )
    assert [c.expression for c in decisiones[0].atomic_conditions] == ["a > 0", "b"]
