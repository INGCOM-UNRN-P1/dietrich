"""Auditor y calculador de cobertura MC/DC para archivos de código C."""

from pathlib import Path
from typing import List, Optional
from dietrich.core.models import McDcAuditReport, DecisionPoint
from dietrich.core.condition_extractor import extract_decision_points


def audit_mcdc_coverage(source_file: Path, min_coverage: float = 100.0) -> McDcAuditReport:
    """Analiza las decisiones lógicas y calcula la cobertura y pares de independencia MC/DC requeridos.

    `min_coverage` es el porcentaje promedio de condiciones con par de independencia
    por debajo del cual el veredicto es negativo (100 exige que todas lo tengan).
    """
    decisions = extract_decision_points(source_file)

    compound_count = len(decisions)
    total_mcdc = sum(d.mcdc_coverage_percent for d in decisions)
    avg_mcdc = (total_mcdc / compound_count) if compound_count > 0 else 100.0

    # El veredicto surge de los pares de independencia realmente hallados: una
    # decisión con condiciones enmascaradas no se puede cubrir por MC/DC y no
    # debe darse por aprobada salvo que el umbral pedido lo permita.
    sin_cubrir = [d for d in decisions if d.missing_independence_pairs]
    aprobado = not sin_cubrir if min_coverage >= 100.0 else round(avg_mcdc, 2) >= min_coverage

    return McDcAuditReport(
        source_file=str(source_file),
        total_decisions_found=compound_count,
        compound_decisions_count=compound_count,
        average_mcdc_coverage=round(avg_mcdc, 2),
        decisions=decisions,
        min_coverage_required=min_coverage,
        passed=aprobado,
    )
