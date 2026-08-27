"""Plugin de DIETRICH para el microkernel RIPLEY."""

from pathlib import Path
from typing import Dict, Any
from dietrich.core.mcdc_analyzer import audit_mcdc_coverage


class DietrichPlugin:
    """Plugin de análisis de cobertura MC/DC para Ripley."""

    name = "mcdc_coverage"
    description = "Validador de cobertura lógica avanzada MC/DC (Modified Condition/Decision Coverage) en C"

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        source_dir = Path(context.get("source_dir", "."))
        main_c = source_dir / "main.c"
        if not main_c.exists():
            return {"passed": True, "decisions_count": 0}

        report = audit_mcdc_coverage(main_c)

        return {
            "passed": report.passed,
            "decisions_count": report.compound_decisions_count,
            "average_coverage": report.average_mcdc_coverage,
            "decisions": [
                {
                    "line": d.line_number,
                    "condition": d.raw_condition,
                    "atomics": [a.model_dump() for a in d.atomic_conditions],
                    "required_vectors": d.required_vectors_count
                }
                for d in report.decisions
            ]
        }
