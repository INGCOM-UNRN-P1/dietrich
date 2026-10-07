"""Cobertura de líneas, ramas y condiciones medida con gcc y gcov (`dietrich lines`).

Es el paso anterior a MC/DC (revisión, 05 §3: «dietrich arranca en MC/DC»): compila las fuentes con
`--coverage`, ejecuta el programa (una vez por cada archivo de entrada) y lee el JSON de gcov para
decir, en términos de la clase, qué líneas no ejecutó ninguna prueba, qué decisiones tomaron un solo
camino y qué funciones nunca se llamaron. Con gcc 14 o posterior mide además las condiciones
(`-fcondition-coverage`) y nombra la condición atómica que nunca fue verdadera o falsa.

Un programa que termina por una señal (un `assert` que falla, un segmentation fault) o que se corta por
tiempo no guarda los datos de cobertura: por eso se le agrega un objeto que los vuelca antes de morir.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

ES_WINDOWS = os.name == "nt"

# Se compila sin --coverage junto al programa: ante una señal vuelca los contadores (__gcov_dump, de
# libgcov) y deja que la señal siga su curso, así el código de salida sigue siendo el de la falla.
VOLCADO_ANTE_SENALES = r"""
#include <signal.h>
extern void __gcov_dump(void);
static void dietrich_volcar(int senal)
{
    __gcov_dump();
    signal(senal, SIG_DFL);
    raise(senal);
}
__attribute__((constructor)) static void dietrich_instalar(void)
{
    signal(SIGABRT, dietrich_volcar);
    signal(SIGSEGV, dietrich_volcar);
    signal(SIGFPE, dietrich_volcar);
    signal(SIGTERM, dietrich_volcar);
#ifdef SIGBUS
    signal(SIGBUS, dietrich_volcar);
#endif
}
"""

RE_MAIN = re.compile(r"\bint\s+main\s*\(")
NOMBRES_DE_SENALES = {int(s): s.name for s in signal.Signals}


class ErrorDeCobertura(Exception):
    """No se pudo medir: falta gcc o gcov, las fuentes no compilan o gcov no entiende los datos."""


class Ejecucion(BaseModel):
    entrada: Optional[str] = None  # archivo usado como entrada estándar
    codigo_salida: Optional[int] = None
    senal: Optional[str] = None  # SIGABRT, SIGSEGV…: la ejecución terminó por una señal
    agoto_tiempo: bool = False


class RamaPendiente(BaseModel):
    linea: int
    codigo: str
    tomadas: int
    total: int


class CondicionPendiente(BaseModel):
    linea: int
    codigo: str
    condicion: str
    nunca_fue: str  # "verdadera" o "falsa"


class FuncionSinLlamar(BaseModel):
    nombre: str
    linea: int
    linea_fin: int


class CoberturaArchivo(BaseModel):
    archivo: str
    lineas_totales: int = 0
    lineas_ejecutadas: int = 0
    ramas_totales: int = 0
    ramas_tomadas: int = 0
    condiciones_totales: Optional[int] = None  # None: el gcc instalado no mide condiciones
    condiciones_cubiertas: Optional[int] = None
    lineas_sin_ejecutar: List[int] = Field(default_factory=list)
    ramas_pendientes: List[RamaPendiente] = Field(default_factory=list)
    condiciones_pendientes: List[CondicionPendiente] = Field(default_factory=list)
    funciones_sin_llamar: List[FuncionSinLlamar] = Field(default_factory=list)


class ReporteLineas(BaseModel):
    schema_version: str = "1.0.0"
    herramienta: str = "dietrich"
    comando: str = "lines"
    gcc: str = ""
    archivos: List[CoberturaArchivo] = Field(default_factory=list)
    ejecuciones: List[Ejecucion] = Field(default_factory=list)
    porcentaje_lineas: float = 100.0
    porcentaje_ramas: Optional[float] = None  # None: no hay decisiones en el código medido
    porcentaje_condiciones: Optional[float] = None
    min_lineas: float = 0.0
    min_ramas: float = 0.0
    aprobado: bool = True


def _porcentaje(parte: int, total: int) -> Optional[float]:
    return round(parte / total * 100.0, 2) if total else None


def _version_gcc(gcc: str) -> Tuple[str, int]:
    res = subprocess.run([gcc, "-dumpfullversion", "-dumpversion"], capture_output=True, text=True)
    texto = res.stdout.strip() or "0"
    try:
        mayor = int(texto.split(".")[0])
    except ValueError:
        mayor = 0
    return texto, mayor


def _ejecutable(directorio: Path) -> Path:
    return directorio / ("programa.exe" if ES_WINDOWS else "programa")


def _correr(programa: Path, entrada: Optional[Path], timeout: float) -> Ejecucion:
    stdin = open(entrada, "rb") if entrada else subprocess.DEVNULL
    try:
        proceso = subprocess.Popen([str(programa)], stdin=stdin, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        try:
            codigo = proceso.wait(timeout=timeout)
            agoto = False
        except subprocess.TimeoutExpired:
            # SIGTERM primero: el volcado ante señales guarda lo que se ejecutó hasta el corte.
            proceso.terminate()
            try:
                codigo = proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proceso.kill()
                codigo = proceso.wait()
            agoto = True
    finally:
        if entrada:
            stdin.close()
    if codigo < 0:
        senal = NOMBRES_DE_SENALES.get(-codigo, f"señal {-codigo}")
    elif ES_WINDOWS and codigo >= 0xC0000000:
        senal = f"excepción 0x{codigo:08X}"  # NTSTATUS: 0xC0000005 es el acceso inválido a memoria
    else:
        senal = None
    return Ejecucion(entrada=str(entrada) if entrada else None, codigo_salida=codigo, senal=senal,
                     agoto_tiempo=agoto)


def _atomos_en_orden(nodo) -> List[str]:
    """Condiciones atómicas de una expresión con && y ||, en el orden en que aparecen (sin deduplicar)."""
    if nodo.type == "parenthesized_expression":
        internos = [c for c in nodo.children if c.type not in ("(", ")")]
        return _atomos_en_orden(internos[0]) if len(internos) == 1 else []
    if nodo.type == "binary_expression":
        operador = nodo.child_by_field_name("operator")
        if operador is not None and operador.text.decode() in ("&&", "||"):
            return _atomos_en_orden(nodo.child_by_field_name("left")) + _atomos_en_orden(nodo.child_by_field_name("right"))
    return [nodo.text.decode("utf-8", errors="replace").strip()]


def condiciones_por_linea(fuente: Path) -> Dict[int, List[List[str]]]:
    """{línea: [condiciones atómicas de cada expresión booleana de la línea]}, para nombrar las de gcov."""
    from dietrich.core.condition_extractor import DECISION_NODES, get_c_parser

    arbol = get_c_parser().parse(fuente.read_bytes())
    expresiones: List[Tuple[int, int, List[str]]] = []

    def es_logica(nodo) -> bool:
        operador = nodo.child_by_field_name("operator") if nodo.type == "binary_expression" else None
        return operador is not None and operador.text.decode() in ("&&", "||")

    def recorrer(nodo, dentro: bool) -> None:
        condicion = nodo.child_by_field_name("condition") if nodo.type in DECISION_NODES else None
        if condicion is not None and not dentro:
            expresiones.append((condicion.start_byte, condicion.start_point.row + 1, _atomos_en_orden(condicion)))
            for hijo in nodo.children:
                recorrer(hijo, hijo == condicion)
            return
        if es_logica(nodo) and not dentro:
            expresiones.append((nodo.start_byte, nodo.start_point.row + 1, _atomos_en_orden(nodo)))
            dentro = True
        for hijo in nodo.children:
            recorrer(hijo, dentro)

    recorrer(arbol.root_node, False)
    por_linea: Dict[int, List[List[str]]] = {}
    for _, linea, atomos in sorted(expresiones):
        por_linea.setdefault(linea, []).append(atomos)
    return por_linea


def _analizar_archivo(datos: dict, fuente: Path, condiciones: bool) -> CoberturaArchivo:
    codigo = fuente.read_text(encoding="utf-8", errors="replace").splitlines()

    def texto(linea: int) -> str:
        return codigo[linea - 1].strip() if 0 < linea <= len(codigo) else ""

    lineas: Dict[int, int] = {}
    ramas: Dict[int, List[int]] = {}
    conjuntos: Dict[int, List[dict]] = {}
    for linea in datos.get("lines", []):
        numero = linea["line_number"]
        lineas[numero] = max(lineas.get(numero, 0), linea["count"])
        cuentas = [r["count"] for r in linea.get("branches", []) if not r.get("throw")]
        if cuentas:
            ramas.setdefault(numero, []).extend(cuentas)
        if linea.get("conditions"):
            conjuntos.setdefault(numero, []).extend(linea["conditions"])

    resultado = CoberturaArchivo(
        archivo=str(fuente),
        lineas_totales=len(lineas),
        lineas_ejecutadas=sum(1 for c in lineas.values() if c > 0),
        lineas_sin_ejecutar=sorted(n for n, c in lineas.items() if c == 0),
        funciones_sin_llamar=[FuncionSinLlamar(nombre=f["name"], linea=f["start_line"],
                                               linea_fin=f.get("end_line", f["start_line"]))
                              for f in datos.get("functions", []) if f.get("execution_count", 0) == 0],
    )
    for numero, cuentas in sorted(ramas.items()):
        resultado.ramas_totales += len(cuentas)
        tomadas = sum(1 for c in cuentas if c > 0)
        resultado.ramas_tomadas += tomadas
        # Una decisión que nunca se evaluó ya aparece como línea sin ejecutar.
        if 0 < tomadas < len(cuentas):
            resultado.ramas_pendientes.append(RamaPendiente(linea=numero, codigo=texto(numero), tomadas=tomadas,
                                                            total=len(cuentas)))
    if condiciones:
        resultado.condiciones_totales = resultado.condiciones_cubiertas = 0
        nombres = condiciones_por_linea(fuente) if conjuntos else {}
        for numero, lista in sorted(conjuntos.items()):
            atomos_de_la_linea = nombres.get(numero, [])
            for i, conjunto in enumerate(lista):
                resultado.condiciones_totales += conjunto["count"]
                resultado.condiciones_cubiertas += conjunto["covered"]
                if lineas.get(numero, 0) == 0:
                    continue  # la línea entera quedó sin ejecutar: ya se reporta así
                cantidad = conjunto["count"] // 2
                atomos = atomos_de_la_linea[i] if (len(atomos_de_la_linea) == len(lista)
                                                    and len(atomos_de_la_linea[i]) == cantidad) else None
                for valor, clave in (("verdadera", "not_covered_true"), ("falsa", "not_covered_false")):
                    for indice in conjunto.get(clave, []):
                        nombre = atomos[indice] if atomos else f"condición {indice + 1} de {cantidad}"
                        resultado.condiciones_pendientes.append(CondicionPendiente(
                            linea=numero, codigo=texto(numero), condicion=nombre, nunca_fue=valor))
    return resultado


def medir_cobertura(
    fuentes: Sequence[Path],
    entradas: Sequence[Path] = (),
    medir: Sequence[Path] = (),
    cflags: Sequence[str] = (),
    timeout: float = 10.0,
    min_lineas: float = 0.0,
    min_ramas: float = 0.0,
    gcc: str = "gcc",
    gcov: str = "gcov",
) -> ReporteLineas:
    """Compila `fuentes` con cobertura, ejecuta el programa y devuelve qué quedó sin ejercitar.

    Se mide `medir`; si no se indica, las fuentes que no definen `main` (el código que prueban las
    pruebas) o, si todas lo definen, todas.
    """
    gcc_bin, gcov_bin = shutil.which(gcc), shutil.which(gcov)
    if not gcc_bin or not gcov_bin:
        faltante = gcc if not gcc_bin else gcov
        raise ErrorDeCobertura(f"no se encontró {faltante}: dietrich lines necesita gcc y su gcov "
                               "(en macOS, el gcc de Homebrew con --gcc gcc-14 --gcov gcov-14).")
    fuentes = [Path(f).resolve() for f in fuentes]
    if medir:
        medidas = [Path(m).resolve() for m in medir]
        ajenas = [m for m in medidas if m not in fuentes]
        if ajenas:
            raise ErrorDeCobertura(f"{ajenas[0].name} no está entre las fuentes a compilar.")
    else:
        sin_main = [f for f in fuentes if not RE_MAIN.search(f.read_text(encoding="utf-8", errors="replace"))]
        medidas = sin_main or list(fuentes)

    version, mayor = _version_gcc(gcc_bin)
    condiciones = mayor >= 14  # -fcondition-coverage existe desde gcc 14
    with tempfile.TemporaryDirectory(prefix="dietrich-") as tmp:
        directorio = Path(tmp)
        objetos: List[Path] = []
        for i, fuente in enumerate(fuentes):
            objeto = directorio / f"{i}_{fuente.stem}.o"
            comando = [gcc_bin, "-c", "--coverage", "-O0", "-g", *cflags, str(fuente), "-o", str(objeto)]
            if condiciones:
                comando.insert(3, "-fcondition-coverage")
            res = subprocess.run(comando, capture_output=True, text=True)
            if res.returncode != 0:
                raise ErrorDeCobertura(f"{fuente.name} no compila:\n{res.stderr.strip()}")
            objetos.append(objeto)
        volcado = directorio / "dietrich_volcado.c"
        volcado.write_text(VOLCADO_ANTE_SENALES, encoding="utf-8")
        programa = _ejecutable(directorio)
        res = subprocess.run([gcc_bin, "--coverage", *[str(o) for o in objetos], str(volcado), "-o", str(programa),
                              "-lm"], capture_output=True, text=True)
        if res.returncode != 0:
            raise ErrorDeCobertura(f"no se pudo enlazar el programa:\n{res.stderr.strip()}")

        ejecuciones = [_correr(programa, Path(e).resolve() if e else None, timeout) for e in (entradas or [None])]

        reporte = ReporteLineas(gcc=version, ejecuciones=ejecuciones, min_lineas=min_lineas, min_ramas=min_ramas)
        for fuente, objeto in zip(fuentes, objetos, strict=False):
            if fuente not in medidas:
                continue
            comando = [gcov_bin, "--json-format", "--stdout", "--branch-counts", "--branch-probabilities",
                       str(objeto)]
            if condiciones:
                comando.insert(1, "--conditions")
            res = subprocess.run(comando, capture_output=True, text=True, cwd=directorio)
            datos_del_archivo = None
            for linea in res.stdout.splitlines():
                if not linea.startswith("{"):
                    continue
                try:
                    documento = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                for archivo in documento.get("files", []):
                    ruta = Path(archivo["file"])
                    if not ruta.is_absolute():
                        ruta = Path(documento.get("current_working_directory", directorio)) / ruta
                    if ruta.resolve() == fuente:
                        datos_del_archivo = archivo
            if datos_del_archivo is None:
                raise ErrorDeCobertura(f"gcov no devolvió datos de {fuente.name} (¿gcc y gcov son de la misma "
                                       f"versión? gcov ≥ 10 hace falta para --json-format):\n{res.stderr.strip()}")
            reporte.archivos.append(_analizar_archivo(datos_del_archivo, fuente, condiciones))

    totales = lambda campo: sum(getattr(a, campo) or 0 for a in reporte.archivos)  # noqa: E731
    reporte.porcentaje_lineas = _porcentaje(totales("lineas_ejecutadas"), totales("lineas_totales")) or 0.0
    if not totales("lineas_totales"):
        reporte.porcentaje_lineas = 100.0
    reporte.porcentaje_ramas = _porcentaje(totales("ramas_tomadas"), totales("ramas_totales"))
    if condiciones:
        reporte.porcentaje_condiciones = _porcentaje(totales("condiciones_cubiertas"), totales("condiciones_totales"))
    reporte.aprobado = (reporte.porcentaje_lineas >= min_lineas
                        and (reporte.porcentaje_ramas is None or reporte.porcentaje_ramas >= min_ramas))
    return reporte


def _trivial(linea: str) -> bool:
    texto = linea.strip()
    return texto in ("", "{", "}", "};") or texto.startswith(("//", "/*", "*"))


def bloques(lineas: Sequence[int], codigo: Sequence[str] = ()) -> List[Tuple[int, int]]:
    """[3, 4, 5, 9] → [(3, 5), (9, 9)]: líneas sin ejecutar consecutivas como un solo bloque.

    Con el código, dos líneas separadas solo por llaves, comentarios o líneas en blanco también van juntas.
    """
    resultado: List[Tuple[int, int]] = []
    for n in sorted(lineas):
        if resultado and all(_trivial(codigo[i - 1]) for i in range(resultado[-1][1] + 1, n)
                             if codigo and i <= len(codigo)) and (codigo or n == resultado[-1][1] + 1):
            resultado[-1] = (resultado[-1][0], n)
        else:
            resultado.append((n, n))
    return resultado
