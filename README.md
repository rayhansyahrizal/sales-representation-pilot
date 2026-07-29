# Sales representation falsification pilot — Phase 0

Reproducible acquisition and row-level forensic audit for the protocol's primary pair only. **No models are trained.** Raw data are ignored and must not be redistributed.

## Reproduce

```bash
uv sync --frozen
uv run python scripts/acquire.py
uv run python scripts/audit.py
uv run pytest -q
```

Sources, URLs, DOI/licenses, and checksums are in `manifests/`. Audit JSON is in `artifacts/audits/`; the modeling gate is `artifacts/gate-report.md`. Retailrocket is non-commercial/share-alike. Derived artifacts contain aggregates only.
