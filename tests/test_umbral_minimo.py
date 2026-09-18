"""Regresión de DIETRICH-D0401: `--min-coverage` era una opción muerta.

Estaba declarada y documentada como "Exigir porcentaje mínimo de cobertura" pero
nada la consultaba: cualquier valor daba el mismo veredicto y el mismo exit code.
"""

import pytest
from typer.testing import CliRunner

from dietrich.cli import app
from dietrich.core.mcdc_analyzer import audit_mcdc_coverage

runner = CliRunner()

# Una decisión limpia (100 %) y otra con `b` enmascarada (50 %): promedio 75 %.
FUENTE = (
    "int f(int a,int b){ if (a && b) return 1; return 0; }\n"
    "int g(int a,int b){ if (a && (b || a)) return 1; return 0; }\n"
)


@pytest.fixture
def archivo(tmp_path):
    ruta = tmp_path / "mixto.c"
    ruta.write_text(FUENTE, encoding="utf-8")
    return ruta


def test_promedio_del_fixture(archivo):
    assert audit_mcdc_coverage(archivo).average_mcdc_coverage == 75.0


@pytest.mark.parametrize(
    "umbral, aprueba",
    [(100.0, False), (76.0, False), (75.0, True), (50.0, True), (0.0, True)],
)
def test_el_umbral_decide_el_veredicto(archivo, umbral, aprueba):
    reporte = audit_mcdc_coverage(archivo, min_coverage=umbral)
    assert reporte.passed is aprueba
    assert reporte.min_coverage_required == umbral


def test_por_defecto_se_exige_cobertura_total(archivo):
    assert audit_mcdc_coverage(archivo).passed is False


@pytest.mark.parametrize("umbral, codigo", [("100", 1), ("90", 1), ("75", 0), ("50", 0)])
def test_el_exit_code_de_la_salida_de_terminal_respeta_el_umbral(archivo, umbral, codigo):
    res = runner.invoke(app, ["analyze", str(archivo), "--min-coverage", umbral])
    assert res.exit_code == codigo


@pytest.mark.parametrize("umbral, codigo", [("90", 1), ("75", 0)])
def test_el_exit_code_de_json_respeta_el_umbral(archivo, umbral, codigo):
    res = runner.invoke(app, ["analyze", str(archivo), "--min-coverage", umbral, "--json"])
    assert res.exit_code == codigo


def test_un_umbral_fuera_de_rango_es_error_de_uso(archivo):
    assert runner.invoke(app, ["analyze", str(archivo), "--min-coverage", "150"]).exit_code == 2
    assert runner.invoke(app, ["analyze", str(archivo), "--min-coverage", "-1"]).exit_code == 2


def test_una_decision_limpia_aprueba_con_el_umbral_por_defecto(tmp_path):
    ruta = tmp_path / "ok.c"
    ruta.write_text("int f(int a,int b){ if (a && b) return 1; return 0; }", encoding="utf-8")
    assert runner.invoke(app, ["analyze", str(ruta)]).exit_code == 0
