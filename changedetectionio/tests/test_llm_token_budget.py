#!/usr/bin/env python3
"""
Tests that verify global LLM token budget counters cannot be tampered with
via the API (watch PUT) or via form submissions (settings page POST).

This is critical for hosted deployments where the operator sets
LLM_TOKEN_BUDGET_MONTH in the container — tenants must not be able
to reset or inflate the counter themselves.
"""

