"""Pytest configuration for path setup."""
import pathlib
import sys

# Add project root (one level above `backend`) to PYTHONPATH so that
# `import backend.app.*` works independent of where pytest is executed.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
