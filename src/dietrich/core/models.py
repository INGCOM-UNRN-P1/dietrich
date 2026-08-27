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


class DecisionPoint(BaseModel):
    file_path: str
    line_number: int
    raw_condition: str
    atomic_conditions: List[AtomicCondition] = Field(default_factory=list)
    required_vectors_count: int = 0
    test_vectors: List[McDcTestCaseVector] = Field(default_factory=list)
    covered_vectors_count: int = 0
    mcdc_coverage_percent: float = 100.0


class McDcAuditReport(BaseModel):
    source_file: str
    total_decisions_found: int = 0
    compound_decisions_count: int = 0
    average_mcdc_coverage: float = 100.0
    decisions: List[DecisionPoint] = Field(default_factory=list)
    passed: bool = True
