# specimen — evidence-gated, evaluator-able preprint for `prompt-optimization`

Run of the `specimen` skill (`Z:\Specimen`) against the repository root
`Z:\prompt-optimization` on **2026-08-28**. Outputs land in this directory.

## How to build

Requires [Tectonic](https://tectonic-typesetting.github.io/) (any recent
version; 0.17.0 used here).

```powershell
& "$env:USERPROFILE\tools\tectonic\tectonic.exe" main.tex   # from .specimen\paper
```

First run downloads packages (needs network); the PDF is `main.pdf`. The last
verification pass was clean: **no undefined references**, no `could not
represent` glyph failures, no overfull box above 6.5pt. A `fontconfig` warning
on Windows is benign.

Overleaf: upload `main.tex` + `sections/` + `refs.bib` as a project; the
paper uses only standard/CTAN packages (see `main.tex` preamble). arXiv:
combine `sections/*.tex` into one file or use `\include`; plain-natbib style is
already set. `figures/pipeline.tikz` is inlined via `\input` in section 4.

## What was produced

- `paper/main.tex` — driver (10 `\input` sections, natbib, `refs.bib`).
- `paper/sections/01-intro` … `10-conclusion` — full draft. **§7
  Evaluation Status was written last**, per the discipline.
- `paper/refs.bib` — 29 entries; **every arXiv ID verified against the live
  export.arxiv.org API on 2026-08-28** (see `References at time of capture`
  in `Z:\Specimen\references\literature-scan.md`; IDs verified with
  `Z:\Specimen\scripts\arxiv_lookup.py`).
- `paper/figures/pipeline.tikz` — pipeline diagram (synthetic proposes /
  real held-out disposes, dashed boundary).

## Evidence basis (Step 0, license in §7)

| Evidence | Location | Status (2026-08-28) |
| --- | --- | --- |
| Test suite | `Z:\prompt-optimization\tests\` | **46/46 pass** |
| CLI transcripts | `Z:\prompt-optimization\output\specimen test 2\` | preserved on disk |
| Hard-gate wiring → gate behavior | `scan.json`, `plan*.txt` | partial gate 0.80065 → README only; strict 0.77 → no supported improvement claimed |

Critical framing: **no empirical measurement of any real language model was
made or claimed.** All pipeline numbers are synthetic attractor outputs.

## Deliberately skipped steps (recorded)

- `.git/info/exclude` and nested `git init` inside `.specimen/` — skipped
  because `Z:\prompt-optimization` is **not a git repository**.
- No real-model evaluation step exists by design — that gap is the paper's
  central finding, not an oversight.

## Handoff checklist for the author

- [ ] Replace the placeholder author/affiliation/email block in `main.tex`.
- [ ] Decide fate of `doc` → follow `arxiv` IK policy if posting.
- [ ] Findings to act on (full list in `paper/sections/09-future-work.tex`):
  1. Fix APE citation in `docs/current/research-landscape.md` (2210.03493 is
     Auto-CoT; APE is 2211.01910).
  2. Build the real-evaluator seam (`Evaluator` protocol + `--backend` hook)
     and make the pipeline refuse to emit selections as claims without a real
     run.
  3. Expose attribution via CLI (`prompt-opt attribute`) with an example value
     function.
  4. Stop sorting the scan display by `synAlign` in
     `src/prompt_optimization/cli.py::_print_human`.
  5. Draft a dated pre-registration before any real-model measurement.
  6. Run ≥2 model families on held-out tasks; report bootstrap intervals.