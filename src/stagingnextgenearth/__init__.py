"""Stagingnextgenearth: reusable infrastructure for production FastAPI services."""

__version__ = "0.1.0"

from .app import create_app

__all__ = ["__version__", "create_app"]
