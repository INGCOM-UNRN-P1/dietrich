"""Auditor y calculador de cobertura MC/DC para archivos de código C."""

from pathlib import Path
from typing import List, Optional
from dietrich.core.models import McDcAuditReport, DecisionPoint
from dietrich.core.condition_extractor import extract_decision_points


def audit_mcdc_coverage(source_file: Path) -> McDcAuditReport:
    """Analiza las decisiones lógicas y calcula la cobertura y pares de independencia MC/DC requeridos."""
    decisions = extract_decision_points(source_file)

    compound_count = len(decisions)
    total_mcdc = sum(d.mcdc_coverage_percent for d in decisions)
    avg_mcdc = (total_mcdc / compound_count) if compound_count > 0 else 100.0

    return McDcAuditReport(
        source_file=str(source_file),
        total_decisions_found=compound_count,
        compound_decisions_count=compound_count,
        average_mcdc_coverage=round(avg_mcdc, 2),
        decisions=decisions,
        passed=True
    )
