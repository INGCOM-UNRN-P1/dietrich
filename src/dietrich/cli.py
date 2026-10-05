"""CLI principal de DIETRICH."""

import json
from pathlib import Path
from typing import List, Optional
import typer
from yutani.cli import crear_app
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from dietrich import __version__
from dietrich.core.models import McDcAuditReport
from dietrich.core.mcdc_analyzer import audit_mcdc_coverage
from dietrich.core.lineas import ErrorDeCobertura, ReporteLineas, bloques, medir_cobertura

# Contrato de línea de comandos del ecosistema (-h/--help, --version/-v, errores de datos como
# mensajes) y textos de Typer en español, desde yutani (N-ECO-14).
app = crear_app(
    "dietrich",
    __version__,
    "Validador de cobertura lógica avanzada MC/DC (Modified Condition/Decision Coverage) en C",
    add_completion=True,
    no_args_is_help=False,
)
console = Console()
console_err = Console(stderr=True)


def generar_seccion_markdown(report: McDcAuditReport) -> str:
    """Genera sección de auditoría de cobertura lógica MC/DC para Dredd."""
    status = "ok" if report.passed else "fail"
    lines = [
        f"<!-- dredd-section: dietrich, tool=dietrich, version=1.0.0, status={status} -->\n",
        "## Cobertura Lógica MC/DC (Dietrich)\n",
    ]
    target_name = Path(report.source_file).name if hasattr(report, "source_file") else getattr(report, "target_file", "source.c")
    lines.append(f"- **Archivo analizado:** `{target_name}`")
    lines.append(f"- **Decisiones compuestas analizadas:** {report.compound_decisions_count}")
    lines.append(f"- **Cobertura MC/DC estimada:** `{report.average_mcdc_coverage}%`\n")
    if not report.decisions:
        lines.append("> [!TIP]\n> **Lógica Simple:** Todas las condiciones y bifurcaciones son atómicas simples (no compuestas).\n")
    else:
        lines.append("| Línea | Condición Compuesta | Condiciones Atómicas | Vectores Req. (k+1) |")
        lines.append("| :---: | :--- | :--- | :---: |")
        for d in report.decisions:
            atomics_str = ", ".join(f"`{a.id}: {a.expression.replace('|', '&#124;')}`" for a in d.atomic_conditions)
            cond_limpia = d.raw_condition.replace("|", "&#124;")
            lines.append(f"| {d.line_number} | `{cond_limpia}` | {atomics_str} | {d.required_vectors_count} |")
        lines.append("")
    return "\n".join(lines)


@app.command("analyze")
@app.command("check")
def analyze(
    target_file: Path = typer.Argument(..., help="Archivo C a auditar por cobertura MC/DC", exists=True),
    min_coverage: float = typer.Option(100.0, "--min-coverage", "-m", min=0.0, max=100.0, help="Porcentaje mínimo de condiciones con par de independencia; por debajo, sale con código 1"),
    json_output: bool = typer.Option(False, "--json", help="Emitir salida en formato JSON estructurado"),
    output_md: Optional[Path] = typer.Option(None, "--md", "--output-md", help="Generar sección de reporte en formato Markdown para fusión en Dredd."),
):
    """Analiza condiciones booleanas compuestas (&&, ||) y calcula los vectores de prueba requeridos para MC/DC."""
    report = audit_mcdc_coverage(target_file, min_coverage=min_coverage)

    if output_md:
        md_text = generar_seccion_markdown(report)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(md_text, encoding="utf-8")
        console.print(f"[bold green]✓ Sección Markdown generada en:[/bold green] {output_md}")
        raise typer.Exit(code=0 if report.passed else 1)

    if json_output:
        print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
        if not report.passed:
            raise typer.Exit(code=1)
        return

    if not report.decisions:
        console.print(Panel(
            f"[bold green]✓ Código sin Decisiones Compuestas Complejas[/bold green]\n"
            f"• Archivo: {target_file.name}\n"
            f"• Todas las bifurcaciones son atómicas simples.",
            title="[bold green]DIETRICH MC/DC Check[/bold green]"
        ))
        return

    table = Table(title=f"Puntos de Decisión MC/DC ({target_file.name})", show_header=True, header_style="bold magenta")
    table.add_column("Línea", style="dim", width=6)
    table.add_column("Condición Compuesta", style="cyan")
    table.add_column("Condiciones Atómicas", style="yellow")
    table.add_column("Vectores MC/DC Req.", style="bold green", justify="right")

    for d in report.decisions:
        atomics_str = "\n".join(f"{a.id}: {a.expression}" for a in d.atomic_conditions)
        table.add_row(
            str(d.line_number),
            d.raw_condition,
            atomics_str,
            f"{d.required_vectors_count} vectores (mínimo teórico N+1 = {d.minimum_vectors})"
        )

    console.print(table)

    # Detalle de vectores de prueba para el primer punto de decisión
    if report.decisions:
        first_d = report.decisions[0]
        v_table = Table(title=f"Tabla de Verdad MC/DC — Línea {first_d.line_number} (`{first_d.raw_condition}`)", show_header=True, header_style="bold blue")
        v_table.add_column("Vector #", style="cyan", width=8)
        for at in first_d.atomic_conditions:
            v_table.add_column(f"{at.id} ({at.expression})", style="white")
        v_table.add_column("Resultado Decisión", style="bold")
        v_table.add_column("Par de Independencia", style="yellow")

        for v in first_d.test_vectors:
            row = [str(v.vector_id)]
            for at in first_d.atomic_conditions:
                val = v.assignments.get(at.id, False)
                if at.id in v.not_evaluated:
                    val_str = "[dim]—[/dim]"  # no se evalúa por el cortocircuito: su valor no importa
                else:
                    val_str = "[green]T[/green]" if val else "[red]F[/red]"
                row.append(val_str)
            res_str = "[bold green]TRUE[/bold green]" if v.outcome else "[bold red]FALSE[/bold red]"
            row.append(res_str)
            row.append(f"Prueba independencia para '{v.is_independence_pair_for}'" if v.is_independence_pair_for else "Vector Base")
            v_table.add_row(*row)

        console.print(v_table)
        console.print("[dim]— : C no evalúa esa condición en ese caso (cortocircuito de && y ||): su valor no importa.[/dim]")

    for d in report.decisions:
        if d.warning:
            console.print(f"[yellow]⚠ Línea {d.line_number}:[/yellow] {d.warning}")

    console.print(Panel(
        f"[bold]Decisiones Compuestas Analizadas:[/bold] {report.compound_decisions_count}\n"
        f"[bold green]Cobertura MC/DC Estimada:[/bold green] {report.average_mcdc_coverage}% "
        f"(umbral exigido: {report.min_coverage_required:g}%)\n"
        f"[dim]↳ Cada condición atómica afecta de forma independiente el resultado final de la decisión.[/dim]",
        title="[bold cyan]DIETRICH MC/DC Summary[/bold cyan]"
    ))
    if not report.passed:
        raise typer.Exit(code=1)


def generar_seccion_lineas(reporte: ReporteLineas) -> str:
    """Sección de cobertura de líneas y ramas para el reporte de Dredd."""
    estado = "ok" if reporte.aprobado else "fail"
    partes = [
        f"<!-- dredd-section: dietrich-lines, tool=dietrich, version=1.0.0, status={estado} -->\n",
        "## Cobertura de líneas y ramas (Dietrich)\n",
        f"- **Líneas ejecutadas:** {reporte.porcentaje_lineas:g} %",
        f"- **Ramas tomadas:** {_pct(reporte.porcentaje_ramas)}",
    ]
    if reporte.porcentaje_condiciones is not None:
        partes.append(f"- **Condiciones cubiertas:** {_pct(reporte.porcentaje_condiciones)}")
    partes.append("")
    for archivo in reporte.archivos:
        nombre = Path(archivo.archivo).name
        en_funciones = {n for f in archivo.funciones_sin_llamar for n in range(f.linea, f.linea_fin + 1)}
        codigo = Path(archivo.archivo).read_text(encoding="utf-8", errors="replace").splitlines()
        for inicio, fin in bloques([n for n in archivo.lineas_sin_ejecutar if n not in en_funciones], codigo):
            rango = f"{inicio}" if inicio == fin else f"{inicio}–{fin}"
            partes.append(f"- `{nombre}:{rango}`: ninguna prueba ejecutó estas líneas.")
        for rama in archivo.ramas_pendientes:
            partes.append(f"- `{nombre}:{rama.linea}`: la decisión tomó {rama.tomadas} de sus {rama.total} caminos.")
        for f in archivo.funciones_sin_llamar:
            partes.append(f"- `{nombre}:{f.linea}`: la función `{f.nombre}` nunca se llamó.")
    partes.append("")
    return "\n".join(partes)


def _pct(valor: Optional[float]) -> str:
    return "sin decisiones" if valor is None else f"{valor:g} %"


@app.command("lines")
def lines_cmd(
    fuentes: List[Path] = typer.Argument(..., help="Fuentes C a compilar juntas: el código y el programa de prueba (con main).", exists=True, dir_okay=False),
    entrada: List[Path] = typer.Option([], "--input", "-i", help="Archivo para la entrada estándar; se repite para varias ejecuciones (una por archivo).", exists=True, dir_okay=False),
    solo: List[Path] = typer.Option([], "--only", help="Fuente a medir (se repite). Por defecto, las que no tienen main.", exists=True, dir_okay=False),
    cflags: str = typer.Option("", "--cflags", help="Banderas extra para gcc, por ejemplo '-std=c11 -Wall'."),
    timeout: float = typer.Option(10.0, "--timeout", min=0.1, help="Segundos por ejecución; al cortarla se guarda lo ejecutado hasta ahí."),
    min_lineas: float = typer.Option(0.0, "--min-lines", min=0.0, max=100.0, help="Porcentaje mínimo de líneas ejecutadas; por debajo, sale con 1."),
    min_ramas: float = typer.Option(0.0, "--min-branches", min=0.0, max=100.0, help="Porcentaje mínimo de ramas tomadas; por debajo, sale con 1."),
    gcc: str = typer.Option("gcc", "--gcc", help="Compilador (gcc-14 en macOS con Homebrew)."),
    gcov: str = typer.Option("gcov", "--gcov", help="gcov de la misma versión que el compilador."),
    json_output: bool = typer.Option(False, "--json", help="Emitir salida en formato JSON estructurado"),
    output_md: Optional[Path] = typer.Option(None, "--md", "--output-md", help="Generar sección de reporte en formato Markdown para fusión en Dredd."),
):
    """Mide qué líneas, ramas y condiciones ejecutan tus pruebas (gcc + gcov): el paso previo a MC/DC."""
    import shlex

    try:
        reporte = medir_cobertura(fuentes, entrada, solo, shlex.split(cflags), timeout, min_lineas, min_ramas,
                                  gcc=gcc, gcov=gcov)
    except ErrorDeCobertura as exc:
        console_err.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(code=2)
    codigo = 0 if reporte.aprobado else 1

    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(generar_seccion_lineas(reporte), encoding="utf-8")
        console.print(f"[bold green]✓ Sección Markdown generada en:[/bold green] {output_md}")
        raise typer.Exit(code=codigo)
    if json_output:
        print(json.dumps(reporte.model_dump(), indent=2, ensure_ascii=False))
        raise typer.Exit(code=codigo)

    for ejecucion in reporte.ejecuciones:
        origen = f"con la entrada {Path(ejecucion.entrada).name}" if ejecucion.entrada else "sin entrada"
        if ejecucion.agoto_tiempo:
            console.print(f"[yellow]⚠ La ejecución {origen} superó {timeout:g} s y se cortó: ¿un bucle que no "
                          "termina? Se cuenta lo ejecutado hasta el corte.[/yellow]")
        elif ejecucion.senal:
            console.print(f"[yellow]⚠ La ejecución {origen} terminó por {ejecucion.senal} (un assert que falla "
                          "da SIGABRT): revisá esa prueba; se cuenta lo ejecutado hasta la falla.[/yellow]")
        elif ejecucion.codigo_salida:
            console.print(f"[dim]La ejecución {origen} terminó con código {ejecucion.codigo_salida}.[/dim]")

    tabla = Table(title="Cobertura de líneas y ramas (gcov)", header_style="bold magenta")
    tabla.add_column("Archivo", style="cyan")
    tabla.add_column("Líneas", justify="right")
    tabla.add_column("Ramas", justify="right")
    if reporte.porcentaje_condiciones is not None:
        tabla.add_column("Condiciones", justify="right")
    for a in reporte.archivos:
        fila = [Path(a.archivo).name, f"{a.lineas_ejecutadas}/{a.lineas_totales}",
                f"{a.ramas_tomadas}/{a.ramas_totales}" if a.ramas_totales else "—"]
        if reporte.porcentaje_condiciones is not None:
            fila.append(f"{a.condiciones_cubiertas}/{a.condiciones_totales}" if a.condiciones_totales else "—")
        tabla.add_row(*fila)
    console.print(tabla)

    for a in reporte.archivos:
        nombre = Path(a.archivo).name
        codigo_fuente = Path(a.archivo).read_text(encoding="utf-8", errors="replace").splitlines()
        # Las líneas de una función que nunca se llamó se informan con la función, no una por una.
        en_funciones = {n for f in a.funciones_sin_llamar for n in range(f.linea, f.linea_fin + 1)}
        sueltas = [n for n in a.lineas_sin_ejecutar if n not in en_funciones]
        if sueltas:
            console.print(f"\n[bold]{nombre}: líneas que ninguna prueba ejecutó[/bold]")
            for inicio, fin in bloques(sueltas, codigo_fuente):
                for n in range(inicio, fin + 1):
                    texto = codigo_fuente[n - 1] if n <= len(codigo_fuente) else ""
                    marca = "[red]✗[/red]" if n in a.lineas_sin_ejecutar else " "
                    console.print(f"[red]{n:>5}[/red] {marca} │ {escape(texto)}")
                console.print("      ┄")
        if a.ramas_pendientes:
            console.print(f"\n[bold]{nombre}: decisiones que tomaron un solo camino[/bold]")
            for r in a.ramas_pendientes:
                console.print(f"[yellow]{r.linea:>5}[/yellow] │ {escape(r.codigo)}  "
                              f"[dim]({r.tomadas} de {r.total} ramas)[/dim]")
        if a.condiciones_pendientes:
            console.print(f"\n[bold]{nombre}: condiciones que nunca decidieron el resultado[/bold]")
            for c in a.condiciones_pendientes:
                console.print(f"[yellow]{c.linea:>5}[/yellow] │ [cyan]{escape(c.condicion)}[/cyan] nunca fue "
                              f"{c.nunca_fue}: agregá una prueba en la que lo sea.")
        if a.funciones_sin_llamar:
            console.print(f"\n[bold]{nombre}: funciones que ninguna prueba llamó[/bold]")
            for f in a.funciones_sin_llamar:
                console.print(f"[red]{f.linea:>5}[/red] │ [bold]{escape(f.nombre)}[/bold] "
                              f"[dim](líneas {f.linea}–{f.linea_fin})[/dim]")

    resumen = [f"[bold]Líneas ejecutadas:[/bold] {reporte.porcentaje_lineas:g} %"
               + (f" (mínimo {min_lineas:g} %)" if min_lineas else ""),
               f"[bold]Ramas tomadas:[/bold] {_pct(reporte.porcentaje_ramas)}"
               + (f" (mínimo {min_ramas:g} %)" if min_ramas else "")]
    if reporte.porcentaje_condiciones is not None:
        resumen.append(f"[bold]Condiciones cubiertas:[/bold] {_pct(reporte.porcentaje_condiciones)}")
    else:
        resumen.append(f"[dim]gcc {reporte.gcc} no mide condiciones (hace falta gcc 14 o posterior).[/dim]")
    resumen.append("[dim]↳ La cobertura dice qué se ejecutó, no si el resultado es correcto: eso lo dicen las "
                   "aserciones. El paso siguiente es MC/DC: dietrich check.[/dim]")
    console.print(Panel("\n".join(resumen), title="[bold cyan]DIETRICH lines[/bold cyan]",
                        border_style="green" if reporte.aprobado else "red"))
    raise typer.Exit(code=codigo)


@app.command("report")
def report_cmd(
    target_file: Path = typer.Argument(..., help="Archivo C a auditar por cobertura MC/DC", exists=True),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Ruta de destino del archivo Markdown."),
):
    """Genera directamente la sección de reporte Markdown de DIETRICH para Dredd."""
    report = audit_mcdc_coverage(target_file)
    md_content = generar_seccion_markdown(report)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(md_content, encoding="utf-8")
        console.print(f"[bold green]✓ Reporte Markdown generado en:[/bold green] {output}")
    else:
        print(md_content)


@app.command("doctor")
def doctor_cmd(
    json_output: bool = typer.Option(False, "--json", help="Emitir diagnóstico en formato JSON estructurado."),
):
    """Verifica el estado del entorno de análisis MC/DC de DIETRICH."""
    import sys

    diagnostico = []

    py_ok = sys.version_info >= (3, 10)
    diagnostico.append({
        "componente": "Python Runtime",
        "estado": "OK" if py_ok else "ERROR",
        "requerido": True,
        "detalle": f"Python {sys.version.split()[0]} (requiere >= 3.10)",
    })

    try:
        from dietrich.core.condition_extractor import get_c_parser
        get_c_parser()
        ts_ok, ts_detalle = True, "Parser Tree-Sitter C y gramática AST operativos"
    except Exception as exc:
        ts_ok, ts_detalle = False, str(exc)
    diagnostico.append({
        "componente": "Tree-Sitter C Parser",
        "estado": "OK" if ts_ok else "ERROR",
        "requerido": True,
        "detalle": ts_detalle,
    })

    # Verificación funcional del motor: una decisión conocida debe dar sus
    # pares de causa única. Detecta una gramática que parsea pero no permite
    # analizar condiciones compuestas.
    motor_ok, motor_detalle = False, "No evaluado"
    if ts_ok:
        try:
            from dietrich.core.boolean_expr import (
                MAX_CONDICIONES,
                construir_expresion,
                pares_de_independencia,
            )
            parser = get_c_parser()
            arbol = parser.parse(b"int f(int a,int b){ if (a && b) return 1; return 0; }")

            def _buscar(n):
                if n.type == "if_statement":
                    return n.child_by_field_name("condition")
                for hijo in n.children:
                    hallado = _buscar(hijo)
                    if hallado:
                        return hallado
                return None

            expresion, textos = construir_expresion(_buscar(arbol.root_node))
            pares = pares_de_independencia(expresion, len(textos))
            motor_ok = len(textos) == 2 and all(p is not None for p in pares.values())
            motor_detalle = (
                f"Pares de causa única operativos (tope de {MAX_CONDICIONES} condiciones por decisión)"
                if motor_ok
                else "El motor no pudo derivar los pares de una decisión de prueba"
            )
        except Exception as exc:
            motor_detalle = str(exc)
    diagnostico.append({
        "componente": "Motor MC/DC",
        "estado": "OK" if motor_ok else "ERROR",
        "requerido": True,
        "detalle": motor_detalle,
    })

    todo_ok = py_ok and ts_ok and motor_ok

    if json_output:
        payload = {
            "schema_version": "1.0.0",
            "herramienta": "dietrich",
            "ok": todo_ok,
            "componentes": diagnostico,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        raise typer.Exit(code=0 if todo_ok else 1)

    tabla = Table(title="🏥 Diagnóstico del Entorno DIETRICH (doctor)", border_style="cyan")
    tabla.add_column("Componente", style="bold white")
    tabla.add_column("Estado", justify="center")
    tabla.add_column("Detalle")

    for componente in diagnostico:
        color = "bold green" if componente["estado"] == "OK" else "bold red"
        simbolo = "✓" if componente["estado"] == "OK" else "✗"
        tabla.add_row(
            componente["componente"],
            f"[{color}]{simbolo} {componente['estado']}[/{color}]",
            componente["detalle"],
        )

    console.print(tabla)
    if not todo_ok:
        raise typer.Exit(code=1)


@app.command()
def version():
    """Muestra la versión de DIETRICH."""
    from dietrich import __version__
    console.print(f"[bold cyan]DIETRICH[/bold cyan] versión [green]{__version__}[/green]")


if __name__ == "__main__":
    app()
