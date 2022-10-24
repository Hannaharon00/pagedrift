#!/bin/bash
# Test script for CLI options - Parallel execution
# Tests -u, -uN, -r, -b flags

set -u  # Exit on undefined variables

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results directory (for parallel safety)
TEST_RESULTS_DIR="/tmp/cli-test-results-$$"
mkdir -p "$TEST_RESULTS_DIR"

