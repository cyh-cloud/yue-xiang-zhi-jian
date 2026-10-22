"""Contracts shared by every site-specific Scrapy project."""

from .admission import AdmissionDecision, evaluate_admission
from .items import CollectionItem, validate_item
from .reporting import RunReport
from .robots import RobotsFact

__all__ = [
    "AdmissionDecision",
    "CollectionItem",
    "RobotsFact",
    "RunReport",
    "evaluate_admission",
    "validate_item",
]
