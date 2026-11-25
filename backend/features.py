"""The installed optional features. The core reaches a feature only through this list and shared/hooks.py.

A feature is a package that depends on the core, never the reverse. Its `feature` module provides:

    install(app)                                  add routes and error handlers
    start(app, config, database, client, **opts)  start services, subscribe to hooks; returns a stop function

Importing it also registers the feature's tables with the metadata and with data management,
and its section of a character card file.
"""

from backend.illustrations import feature as illustrations
from backend.recall import feature as recall
from backend.status_bar import feature as status_bar

FEATURES = (illustrations, recall, status_bar)
