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

# Cleanup function
cleanup() {
    echo ""
    echo "=== Cleaning up test directories ==="
    rm -rf /tmp/cli-test-* 2>/dev/null || true
    rm -rf "$TEST_RESULTS_DIR" 2>/dev/null || true
    # Kill any hanging processes
    pkill -f "changedetection.py.*cli-test" 2>/dev/null || true
}
trap cleanup EXIT

# Helper to record test result
record_result() {
    local test_num=$1
    local status=$2  # pass or fail
    local message=$3

    echo "$status|$message" > "$TEST_RESULTS_DIR/test_${test_num}.result"
}

# Run a test in background
run_test() {
    local test_num=$1
    local test_name=$2
    local test_func=$3

    (
        echo -e "${YELLOW}[Test $test_num]${NC} $test_name"
        if $test_func "$test_num"; then
            record_result "$test_num" "pass" "$test_name"
            echo -e "${GREEN}✓ PASS${NC}: $test_name"
        else
            record_result "$test_num" "fail" "$test_name"
            echo -e "${RED}✗ FAIL${NC}: $test_name"
        fi
    ) &
}

# =============================================================================
# Test Functions (each runs independently)
# =============================================================================

test_help_flag() {
    local test_id=$1
    timeout 3 python3 changedetection.py --help 2>&1 | grep -q "Add URLs on startup"
}

test_version_flag() {
    local test_id=$1
    timeout 3 python3 changedetection.py --version 2>&1 | grep -qE "changedetection.io [0-9]+\.[0-9]+"
}

test_single_url() {
    local test_id=$1
    local dir="/tmp/cli-test-single-${test_id}-$$"
    timeout 10 python3 changedetection.py -d "$dir" -C -u https://example.com -b &>/dev/null
    # Count watch directories (UUID directories containing watch.json)
    [ "$(find "$dir" -mindepth 2 -maxdepth 2 -name 'watch.json' | wc -l)" -eq 1 ]
}

