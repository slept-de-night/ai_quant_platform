"""
Financial Knowledge models and metric explanation schemas.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MetricCategory(str, Enum):
    VALUATION = "valuation"
    FORENSIC = "forensic"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    EXECUTION = "execution"
    MACRO = "macro"


class FinancialMetricExplanation(BaseModel):
    id: str = Field(..., description="Unique identifier for the financial metric")
    name: str = Field(..., description="Human-readable formal name")
    category: MetricCategory = Field(..., description="Domain category")
    summary: str = Field(..., description="1-2 sentence plain-language definition")
    formula: str = Field(..., description="Mathematical or LaTeX representation")
    interpretation: str = Field(..., description="Guidance on what high/low/normal values indicate")
    quant_usage: str = Field(..., description="How the platform quantitative engine uses this metric")
    pitfalls: str = Field(..., description="Common misinterpretations, blind spots, or edge cases")
    ranges: Dict[str, str] = Field(default_factory=dict, description="Concrete benchmark ranges (e.g., Safe, Distress)")
    related_metrics: List[str] = Field(default_factory=list, description="IDs of correlated or complementary metrics")
