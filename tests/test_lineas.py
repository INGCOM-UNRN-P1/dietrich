"""`dietrich lines`: cobertura de líneas, ramas y condiciones con gcc y gcov (revisión, 05 §3)."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from dietrich.cli import app
from dietrich.core.lineas import ErrorDeCobertura, _version_gcc, bloques, medir_cobertura

runner = CliRunner()
pytestmark = pytest.mark.skipif(not (shutil.which("gcc") and shutil.which("gcov")), reason="hace falta gcc y gcov")

CODIGO = """\
#include <stdlib.h>

int suma_positivos(const int *v, int n)
{
    int total = 0;
    if (v == NULL || n < 0) {
        return -1;
    }
    for (int i = 0; i < n; i++) {
        if (v[i] > 0) {
            total += v[i];
        }
    }
    return total;
}

int doble(int x)
{
    return x * 2;
}
"""

PRUEBA = """\
#include <assert.h>
int suma_positivos(const int *v, int n);
int main(void)
{
    int v[] = {1, 2, 3};
    assert(suma_positivos(v, 3) == 6);
    return 0;
}
"""


def _escribir(tmp_path: Path, **archivos: str) -> list:
    rutas = []
    for nombre, contenido in archivos.items():
        ruta = tmp_path / f"{nombre}.c"
        ruta.write_text(contenido, encoding="utf-8")
        rutas.append(ruta)
    return rutas


def test_reporta_lineas_ramas_y_funciones_sin_ejercitar(tmp_path):
    codigo, prueba = _escribir(tmp_path, lista=CODIGO, test_lista=PRUEBA)
    reporte = medir_cobertura([codigo, prueba])
    # Se mide el código probado, no el programa de prueba (el que tiene main).
    assert [Path(a.archivo).name for a in reporte.archivos] == ["lista.c"]
    archivo = reporte.archivos[0]
    assert 7 in archivo.lineas_sin_ejecutar and 5 not in archivo.lineas_sin_ejecutar
    assert [f.nombre for f in archivo.funciones_sin_llamar] == ["doble"]
    assert {r.linea for r in archivo.ramas_pendientes} == {6, 10}
    assert 0 < reporte.porcentaje_lineas < 100 and reporte.aprobado
    assert reporte.ejecuciones[0].codigo_salida == 0


@pytest.mark.skipif(shutil.which("gcc") and _version_gcc(shutil.which("gcc"))[1] < 14,
                    reason="-fcondition-coverage existe desde gcc 14")
def test_nombra_las_condiciones_que_nunca_decidieron(tmp_path):
    codigo, prueba = _escribir(tmp_path, lista=CODIGO, test_lista=PRUEBA)
    archivo = medir_cobertura([codigo, prueba]).archivos[0]
    pendientes = {(c.linea, c.condicion, c.nunca_fue) for c in archivo.condiciones_pendientes}
    assert (6, "v == NULL", "verdadera") in pendientes
    assert (6, "n < 0", "verdadera") in pendientes
    assert (10, "v[i] > 0", "falsa") in pendientes


def test_una_ejecucion_por_entrada_suma_cobertura(tmp_path):
    (fuente,) = _escribir(tmp_path, signo="""\
#include <stdio.h>
int main(void)
{
    int x = 0;
    if (scanf("%d", &x) == 1 && x < 0) {
        printf("negativo\\n");
    } else {
        printf("no negativo\\n");
    }
    return 0;
}
""")
    (tmp_path / "neg.txt").write_text("-3\n", encoding="utf-8")
    (tmp_path / "pos.txt").write_text("4\n", encoding="utf-8")
    solo_una = medir_cobertura([fuente], [tmp_path / "pos.txt"])
    assert solo_una.archivos[0].lineas_sin_ejecutar == [6]
    las_dos = medir_cobertura([fuente], [tmp_path / "neg.txt", tmp_path / "pos.txt"])
    assert las_dos.archivos[0].lineas_sin_ejecutar == [] and len(las_dos.ejecuciones) == 2


def test_un_assert_que_falla_no_pierde_la_cobertura(tmp_path):
    codigo, prueba = _escribir(tmp_path, lista=CODIGO, test_lista=PRUEBA.replace("== 6", "== 7"))
    reporte = medir_cobertura([codigo, prueba])
    assert reporte.ejecuciones[0].senal == "SIGABRT"
    # Sin el volcado ante señales, gcov daría todo el archivo como no ejecutado.
    assert 5 not in reporte.archivos[0].lineas_sin_ejecutar


def test_un_bucle_infinito_se_corta_y_cuenta_lo_ejecutado(tmp_path):
    (fuente,) = _escribir(tmp_path, bucle="""\
int main(void)
{
    volatile int x = 0;
    while (1) {
        x++;
    }
    return 0;
}
""")
    reporte = medir_cobertura([fuente], timeout=0.5)
    assert reporte.ejecuciones[0].agoto_tiempo
    assert 5 not in reporte.archivos[0].lineas_sin_ejecutar


def test_errores_de_uso(tmp_path):
    (roto,) = _escribir(tmp_path, roto="int main(void) { return 0 }\n")
    with pytest.raises(ErrorDeCobertura, match="no compila"):
        medir_cobertura([roto])
    res = runner.invoke(app, ["lines", str(roto)])
    assert res.exit_code == 2 and "no compila" in res.output
    with pytest.raises(ErrorDeCobertura, match="no se encontró"):
        medir_cobertura([roto], gcc="gcc-que-no-existe")


def test_cli_umbral_y_json(tmp_path):
    codigo, prueba = _escribir(tmp_path, lista=CODIGO, test_lista=PRUEBA)
    res = runner.invoke(app, ["lines", str(codigo), str(prueba)])
    assert res.exit_code == 0, res.output
    res = runner.invoke(app, ["lines", str(codigo), str(prueba), "--min-lines", "100", "--json"])
    assert res.exit_code == 1
    datos = json.loads(res.stdout)
    assert datos["schema_version"] == "1.0.0" and datos["comando"] == "lines" and not datos["aprobado"]
    res = runner.invoke(app, ["lines", str(codigo), str(prueba), "--only", str(prueba), "--json"])
    assert [Path(a["archivo"]).name for a in json.loads(res.stdout)["archivos"]] == ["test_lista.c"]


def test_bloques_de_lineas():
    assert bloques([3, 4, 5, 9]) == [(3, 5), (9, 9)]
    codigo = ["a", "b", "x;", "}", "", "y;", "z;"]
    assert bloques([3, 6], codigo) == [(3, 6)]
    assert bloques([3, 7], codigo) == [(3, 3), (7, 7)]
