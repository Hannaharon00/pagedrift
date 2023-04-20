#!/usr/bin/env python3
"""
Comprehensive security and edge case tests for the API.
Tests critical areas that were identified as gaps in the existing test suite.
"""

def is_valid_uuid(val):
    try:
        uuid_module.UUID(str(val))
        return True
    except ValueError:
        return False


