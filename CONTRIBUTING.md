# Contributing

Prompt Optimization is an alpha-stage research tool. Changes should preserve
its central evidence boundary: synthetic scores may propose candidates, but
only held-out behavioral evaluation may support an improvement claim.

## Local setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
```

On a restricted Windows runner, point pytest's temporary directory at a
writable location if the system temp directory is unavailable:

```powershell
python -m pytest --basetemp "$env:TEMP\prompt-optimization-tests"
```

## Change checklist

- Add or update tests for behavior changes.
- Keep CLI JSON stable unless the change is intentionally breaking.
- Update `README.md` for user-visible changes and `docs/STATUS.md` for project
  state changes.
- Label synthetic results as synthetic and proposal-only.
- Preserve run inputs, seeds, evaluator identity, and provenance for empirical
  claims.
- Do not commit virtual environments, caches, or generated package metadata.

## Documentation map

Start at [`docs/README.md`](docs/README.md). Architecture documents describe
design intent; the benchmark card and status page describe what has actually
been demonstrated.
