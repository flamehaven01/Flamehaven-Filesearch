"""
FLAMEHAVEN FileSearch
=====================

Open source semantic document search powered by Google Gemini
Fast, simple, and transparent file search for developers
"""

__version__ = "1.0.0"
__author__ = "FLAMEHAVEN"
__license__ = "MIT"

from .config import Config
from .core import FlamehavenFileSearch

__all__ = ["FlamehavenFileSearch", "Config"]
