"""Illustration feature: everything from image workflows to generated files lives in this package.

The core knows it only through `feature.py` (wired in main.py), the generic hooks in
shared/hooks.py, and the data-management table registry. Nothing here is required for writing or
archiving, and this package depends on the core, never the reverse.
"""
