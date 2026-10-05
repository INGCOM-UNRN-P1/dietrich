"""Modelos de datos para el análisis de cobertura lógica MC/DC en DIETRICH."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AtomicCondition(BaseModel):
    id: str  # "A", "B", "C"
    expression: str  # "x > 0", "y == 2"


class McDcTestCaseVector(BaseModel):
    vector_id: int
    assignments: Dict[str, bool]  # {"A": True, "B": False}
    outcome: bool
    is_independence_pair_for: Optional[str] = None  # "A", "B", etc.
    # Condiciones que C no llega a evaluar con este vector por el cortocircuito de && y || (QoL #245):
    # su valor no importa.
    not_evaluated: List[str] = Field(default_factory=list)


class DecisionPoint(BaseModel):
    file_path: str
    line_number: int
    raw_condition: str
    atomic_conditions: List[AtomicCondition] = Field(default_factory=list)
    required_vectors_count: int = 0
    test_vectors: List[McDcTestCaseVector] = Field(default_factory=list)
    covered_vectors_count: int = 0
    mcdc_coverage_percent: float = 100.0
    # Condiciones sin par de independencia de causa única (enmascaradas o
    # acopladas): es lo que el README promete como "pares faltantes".
    missing_independence_pairs: List[str] = Field(default_factory=list)
    # Cota mínima teórica: N + 1 vectores para N condiciones (QoL #247).
    minimum_vectors: int = 0
    # Aviso pedagógico cuando la decisión combina más de 4 condiciones (QoL #250).
    warning: Optional[str] = None


class McDcAuditReport(BaseModel):
    schema_version: str = "1.1.0"
    source_file: str
    compound_decisions_count: int = 0
    average_mcdc_coverage: float = 100.0
    min_coverage_required: float = 100.0
    decisions: List[DecisionPoint] = Field(default_factory=list)
    passed: bool = True
