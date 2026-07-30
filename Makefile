.PHONY: help install install-dev verify test check integrity clean

PYTHON ?= python3

help:
	@echo "GIFT MCQ Benchmark — Tier 1"
	@echo ""
	@echo "  make verify       re-derive all statistics from the raw DB and assert the audit findings"
	@echo "  make test         run the regression tests (needs: make install-dev)"
	@echo "  make integrity    verify the ground-truth database checksum"
	@echo "  make check        integrity + verify + test"
	@echo ""
	@echo "  make install      install the harness (for running the benchmark live)"
	@echo "  make install-dev  install with test dependencies"
	@echo "  make clean        remove caches and build artifacts (never touches data/)"
	@echo ""
	@echo "'make verify' needs no dependencies at all — the script is stdlib-only."

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

# Stdlib-only; opens data/medrag_eval.sqlite read-only.
verify:
	$(PYTHON) rescore_with_fixed_parser.py --check

test:
	$(PYTHON) -m pytest

# Guards the reproduction anchor. A mismatch means the DB was modified — every
# published figure is derived from it, so re-clone rather than proceeding.
integrity:
	@echo "expected: c6eb43ede71c1c61ffa87f96e5e070f7"
	@printf "actual:   " && \
	  ( md5 -q data/medrag_eval.sqlite 2>/dev/null || md5sum data/medrag_eval.sqlite | cut -d' ' -f1 )

check: integrity verify test

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache build dist *.egg-info code/*.egg-info
