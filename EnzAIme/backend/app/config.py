"""
backend/app/config.py
========================
Thin re-export of the shared enzaime_core configuration, plus a couple of
backend-only settings (app name/version). Keeps a single source of truth
for scientific/business parameters (common/enzaime_core/config.py) while
letting the backend layer add web-server-specific settings.
"""
from enzaime_core import config as core_config  # noqa: F401

APP_NAME = "ENZAIme API"
APP_VERSION = "0.1.0-mvp"
APP_DESCRIPTION = (
    "Environment-Aware AI-Based Enzyme Suitability Prediction, Recommendation "
    "and Mutation Optimization System — in-silico decision-support API."
)
