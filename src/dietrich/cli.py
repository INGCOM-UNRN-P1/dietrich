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
    lines = ["## Cobertura Lógica MC/DC (Dietrich)\n"]
    lines.append(f"- **Archivo analizado:** `{Path(report.target_file).name}`")
    lines.append(f"- **Decisiones compuestas analizadas:** {report.compound_decisions_count}")
    lines.append(f"- **Cobertura MC/DC estimada:** `{report.average_mcdc_coverage}%`\n")
    if not report.decisions:
        lines.append("> [!TIP]\n> **Lógica Simple:** Todas las condiciones y bifurcaciones son atómicas simples (no compuestas).\n")
    else:
        lines.append("| Línea | Condición Compuesta | Condiciones Atómicas | Vectores Req. (k+1) |")
        lines.append("| :---: | :--- | :--- | :---: |")
        for d in report.decisions:
            atomics_str = ", ".join(f"`{a.id}: {a.expression}`" for a in d.atomic_conditions)
            lines.append(f"| {d.line_number} | `{d.raw_condition}` | {atomics_str} | {d.required_vectors_count} |")
        lines.append("")
    return "\n".join(lines)


@app.command("analyze")
@app.command("check")
def analyze(
    target_file: Path = typer.Argument(..., help="Archivo C a auditar por cobertura MC/DC", exists=True),
    min_coverage: float = typer.Option(80.0, "--min-coverage", "-m", help="Porcentaje mínimo de cobertura MC/DC"),
    json_output: bool = typer.Option(False, "--json", help="Emitir salida en formato JSON estructurado"),
    output_md: Optional[Path] = typer.Option(None, "--md", "--output-md", help="Generar sección de reporte en formato Markdown para fusión en Dredd."),
):
    """Analiza condiciones booleanas compuestas (&&, ||) y calcula los vectores de prueba requeridos para MC/DC."""
    report = audit_mcdc_coverage(target_file)

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
        f"[bold green]Cobertura MC/DC Estimada:[/bold green] {report.average_mcdc_coverage}%\n"
        f"[dim]↳ Cada condición atómica afecta de forma independiente el resultado final de la decisión.[/dim]",
        title="[bold cyan]DIETRICH MC/DC Summary[/bold cyan]"
    ))


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


@app.command()
def version():
    """Muestra la versión de DIETRICH."""
    from dietrich import __version__
    console.print(f"[bold cyan]DIETRICH[/bold cyan] versión [green]{__version__}[/green]")


if __name__ == "__main__":
    app()
