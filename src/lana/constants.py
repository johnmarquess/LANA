"""Shared domain constants used across modules (single source of truth)."""

from __future__ import annotations

# Dimension-id fragments that identify the geography dimension across GCP/SEIFA dataflows.
GEO_HINTS = ("REGION", "ASGS", "SA2", "SA1", "SA3", "SA4", "LGA", "STE")

# SEIFA index code -> friendly snake_case prefix.
SEIFA_INDEXES = {"IRSD": "irsd", "IRSAD": "irsad", "IER": "ier", "IEO": "ieo"}
