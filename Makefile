.PHONY: install test check eval
install: ; python -m venv .venv && .venv/bin/pip install -e ".[dev]"
test:    ; .venv/bin/pytest -q
check:   ; .venv/bin/cbc check --terms data/expected/C-001.json --invoices data/invoices/C-001.json || true
eval:    ; .venv/bin/cbc eval
