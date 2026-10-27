"""Ola 13: `dietrich lines --por-entrada` da la huella de cada entrada (lo que usa `tyrell cubrir`)."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dietrich.cli import app
from dietrich.core.lineas import medir_cobertura

pytestmark = pytest.mark.skipif(not (shutil.which("gcc") and shutil.which("gcov")), reason="hace falta gcc y gcov")

PROGRAMA = """\
#include <stdio.h>

int main(void)
{
    int n = 0;
    if (scanf("%d", &n) != 1) {
        return 1;
    }
    if (n > 100) {
        printf("grande\\n");
    } else {
        printf("chico\\n");
    }
    return 0;
}
"""


@pytest.fixture
def programa(tmp_path: Path):
    fuente = tmp_path / "prog.c"
    fuente.write_text(PROGRAMA, encoding="utf-8")
    entradas = []
    for nombre, texto in (("chico", "5\n"), ("grande", "500\n"), ("otro_chico", "7\n")):
        e = tmp_path / f"{nombre}.in"
        e.write_text(texto, encoding="utf-8")
        entradas.append(e)
    return fuente, entradas


def test_cada_entrada_tiene_su_huella_y_el_total_no_cambia(programa):
    fuente, entradas = programa
    con = medir_cobertura([fuente], entradas, por_entrada=True)
    sin = medir_cobertura([fuente], entradas)

    assert sin.huellas is None
    assert [Path(h.entrada).stem for h in con.huellas] == ["chico", "grande", "otro_chico"]
    chico, grande, otro = con.huellas
    assert "prog.c:10" in grande.lineas and "prog.c:10" not in chico.lineas
    assert "prog.c:12" in chico.lineas and "prog.c:12" not in grande.lineas
    # Dos entradas que recorren el mismo camino dejan la misma huella: la segunda no suma nada.
    assert (chico.lineas, chico.ramas) == (otro.lineas, otro.ramas)
    assert set(grande.ramas) - set(chico.ramas)
    # El agregado es el mismo que sin --por-entrada (los contadores se reinician entre huellas).
    assert con.archivos[0].model_dump() == sin.archivos[0].model_dump()


def test_cli_por_entrada_en_json(programa):
    fuente, entradas = programa
    res = CliRunner().invoke(app, ["lines", str(fuente), "-i", str(entradas[0]), "--por-entrada", "--json"])
    assert res.exit_code == 0, res.output
    datos = json.loads(res.output)
    assert len(datos["huellas"]) == 1 and datos["huellas"][0]["lineas"]
