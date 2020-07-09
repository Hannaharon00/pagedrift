"""
Schema utilities for Watch and Tag models.

Provides functions to extract readonly fields and properties from OpenAPI spec.
Shared by both the model layer and API layer to avoid circular dependencies.
"""

import functools


