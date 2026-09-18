"""CLI principal de DIETRICH."""

import json
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from dietrich.core.models import McDcAuditReport
from dietrich.core.mcdc_analyzer import audit_mcdc_coverage

app = typer.Typer(
    name="dietrich",
    help="Validador de cobertura lógica avanzada MC/DC (Modified Condition/Decision Coverage) en C",
    add_completion=True
)
console = Console()


def generar_seccion_markdown(report: McDcAuditReport) -> str:
    """Genera sección de auditoría de cobertura lógica MC/DC para Dredd."""
    lines = [
        "<!-- dredd-section: dietrich v1.0.0 -->\n",
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
            f"{d.required_vectors_count} vectores (k+1)"
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
                val_str = "[green]T[/green]" if val else "[red]F[/red]"
                row.append(val_str)
            res_str = "[bold green]TRUE[/bold green]" if v.outcome else "[bold red]FALSE[/bold red]"
            row.append(res_str)
            row.append(f"Prueba independencia para '{v.is_independence_pair_for}'" if v.is_independence_pair_for else "Vector Base")
            v_table.add_row(*row)

        console.print(v_table)

    console.print(Panel(
        f"[bold]Decisiones Compuestas Analizadas:[/bold] {report.compound_decisions_count}\n"
        f"[bold green]Cobertura MC/DC Estimada:[/bold green] {report.average_mcdc_coverage}% "
        f"(umbral exigido: {report.min_coverage_required:g}%)\n"
        f"[dim]↳ Cada condición atómica afecta de forma independiente el resultado final de la decisión.[/dim]",
        title="[bold cyan]DIETRICH MC/DC Summary[/bold cyan]"
    ))
    if not report.passed:
        raise typer.Exit(code=1)


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
