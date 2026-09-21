"""
enzaime_core
============
Shared, framework-agnostic core logic for the ENZAIme project:
  - config       : all tunable parameters
  - data_loader  : data abstraction layer (Section 4/19)
  - scoring      : transparent compatibility engine (Section 11-12)
  - mutation     : mutation prioritization module (Section 20-22)
  - embeddings   : ESM-2 embedding pipeline helpers (Section 9)
  - model        : small neural suitability model (Section 13)

This package is imported by both `scripts/` (offline pipeline / Kaggle
notebook) and `backend/app` (FastAPI service) so there is exactly one
implementation of the scientific logic.
"""
__version__ = "0.1.0"
