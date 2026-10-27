"""Ola 13 (QoL #250): `dietrich mcdc` emite la tabla de verdad con condiciones enmascaradas y redundantes."""

from pathlib import Path

from typer.testing import CliRunner

from dietrich.cli import app
from dietrich.core.tabla_verdad import markdown, tablas_de_verdad

FUENTE = """int f(int a, int b, int c, int *p)
{
    if (p != 0 && *p > 0 && a < 10)
        return 1;
    if (a > 0 || (a > 0 && b > 0))
        return 2;
    while ((a && b) || (a && c))
        a--;
    if (a > 1)
        return 3;
    return 0;
}
"""


def _tablas(tmp_path: Path):
    fuente = tmp_path / "f.c"
    fuente.write_text(FUENTE, encoding="utf-8")
    return fuente, tablas_de_verdad(fuente)


def test_cadena_de_and_con_cortocircuito(tmp_path):
    _, tablas = _tablas(tmp_path)
    t = tablas[0]
    assert t.linea == 3 and [a for _, a in t.atomos] == ["p != 0", "*p > 0", "a < 10"]
    # Cuatro filas (N + 1): las que difieren sólo en condiciones no evaluadas se juntan.
    assert [f.valores for f in t.filas] == [[False, None, None], [True, False, None], [True, True, False],
                                             [True, True, True]]
    assert [f.deciden for f in t.filas] == [["A"], ["B"], ["C"], ["A", "B", "C"]]
    assert t.filas[2].enmascaradas == ["A", "B"]
    assert all(f.mcdc_para for f in t.filas) and not t.redundantes


def test_condicion_redundante_y_enmascarada(tmp_path):
    _, tablas = _tablas(tmp_path)
    redundante, acoplada = tablas[1], tablas[2]
    assert redundante.redundantes == ["B"]
    assert acoplada.redundantes == []
    assert {e for f in acoplada.filas for e in f.enmascaradas} == {"A", "B"}
    # La decisión simple (a > 1) no se tabula.
    assert [t.linea for t in tablas] == [3, 5, 7]


def test_markdown_y_cli(tmp_path):
    fuente, tablas = _tablas(tmp_path)
    texto = markdown(fuente, tablas)
    assert "| 1 | F | — | — | **F** | A | — | ✓ (A) |" in texto
    assert "**Condición redundante:** B (`b > 0`)" in texto
    assert "`a > 0 &#124;&#124; (a > 0 && b > 0)`" in texto
    destino = tmp_path / "tablas.md"
    res = CliRunner().invoke(app, ["mcdc", str(fuente), "-o", str(destino)])
    assert res.exit_code == 1  # hay una condición redundante
    assert destino.read_text(encoding="utf-8") == texto


def test_sin_decisiones_compuestas(tmp_path):
    fuente = tmp_path / "g.c"
    fuente.write_text("int g(int a) { if (a > 0) return 1; return 0; }\n", encoding="utf-8")
    res = CliRunner().invoke(app, ["mcdc", str(fuente)])
    assert res.exit_code == 0 and "no hay nada que combinar" in res.output
