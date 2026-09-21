"""Regresiones de DIETRICH-D0201 (campo redundante) y D0202 (código sólo de tests)."""

from dietrich.core import condition_extractor
from dietrich.core.mcdc_analyzer import audit_mcdc_coverage as _analizar


def test_reporte_no_duplica_el_conteo_de_decisiones(tmp_path):
    c = tmp_path / "a.c"
    c.write_text("int f(int a, int b) { if (a && b) return 1; return 0; }\n")
    datos = _analizar(c).model_dump()
    assert "total_decisions_found" not in datos
    assert datos["compound_decisions_count"] == 1


def test_no_quedan_extractores_solo_de_tests():
    assert not hasattr(condition_extractor, "split_atomic_conditions")
    assert not hasattr(condition_extractor, "extract_atomics_from_ast")
