"""Tests unitarios y de integración para DIETRICH."""

from pathlib import Path
from typer.testing import CliRunner
from dietrich.cli import app
from dietrich.core.condition_extractor import split_atomic_conditions, extract_decision_points
from dietrich.core.mcdc_analyzer import audit_mcdc_coverage
from dietrich.plugins.ripley_plugin import DietrichPlugin

runner = CliRunner()


def test_split_atomic_conditions():
    cond = "a > 0 && b <= 10 || c == 3"
    atomics = split_atomic_conditions(cond)
    assert len(atomics) == 3
    assert "a > 0" in atomics
    assert "b <= 10" in atomics
    assert "c == 3" in atomics


def test_extract_decision_points_mcdc(tmp_path):
    c = tmp_path / "logica.c"
    c.write_text("""
    #include <stdbool.h>
    bool validar(int edad, bool tiene_permiso) {
        if (edad >= 18 && tiene_permiso) {
            return true;
        }
        return false;
    }
    """)
    decisions = extract_decision_points(c)
    assert len(decisions) == 1
    d = decisions[0]
    assert len(d.atomic_conditions) == 2
    assert d.required_vectors_count == 3  # k + 1 = 2 + 1 = 3


def test_audit_mcdc_coverage(tmp_path):
    c = tmp_path / "app.c"
    c.write_text("int main(void) { if (1 && 0) return 1; return 0; }")
    report = audit_mcdc_coverage(c)
    assert report.passed is True
    assert report.compound_decisions_count == 1


def test_cli_analyze_json(tmp_path):
    c = tmp_path / "main.c"
    c.write_text("int main(void) { if (x > 0 && y < 5) return 1; return 0; }")
    res = runner.invoke(app, ["analyze", str(c), "--json"])
    assert res.exit_code == 0
    assert '"average_mcdc_coverage": 100.0' in res.output


def test_cli_version():
    res = runner.invoke(app, ["version"])
    assert res.exit_code == 0
    assert "DIETRICH" in res.output


def test_ripley_plugin(tmp_path):
    c = tmp_path / "main.c"
    c.write_text("int main(void) { return 0; }")
    plugin = DietrichPlugin()
    res = plugin.run({"source_dir": str(tmp_path)})
    assert res["passed"] is True
