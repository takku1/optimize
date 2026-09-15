# Calibration protocol v0.1

This protocol is preregistered as an implementation contract before any
calibration results are interpreted. Calibration data must be kept separate
from development and sealed test results.

## Design

- Unit: one blinded artifact/scenario bundle, identified as `S###`.
- Panel: every rater scores every artifact in the calibration set.
- Numeric fields: the eight core 0–10 dimensions.
- Categorical field: maturity stage 0–9.
- Required metadata: artifact ID, project type, rater ID, rubric version,
  confidence, rationale, timestamp, and evidence tier.
- Store raw rows unchanged; publish only derived summaries and remove sensitive
  project text from any shared report.

## Analysis

`prompt_optimization.calibration.agreement_report()` reports:

- ICC(2,1), two-way random-effects absolute agreement, single measure, for
  each numeric dimension;
- Fleiss' kappa for maturity stage;
- 95% subject-bootstrap intervals for each ICC;
- panel size, artifact count, complete-crossing status, and explicit limits.

The exact ICC form is declared because different ICC models answer different
questions. Agreement is reliability evidence only; it is not evidence that the
rubric measures the right construct. Use content review and relations to
external outcomes for validity.

## Provisional decision rules

These are frozen for the first calibration run and may only change in a new
protocol version:

- report every dimension, including low or negative estimates;
- flag an ICC dimension when its point estimate is below 0.75 or its lower 95%
  bound is below 0.60;
- flag stage agreement when Fleiss' kappa is below 0.67;
- do not pool flagged dimensions into a single pass result;
- investigate disagreement cases before changing weights, anchors, or wording.

The thresholds are operational gates, not universal laws. Koo and Li recommend
reporting the ICC model, type, definition, software, and confidence interval;
Hallgren documents the need to match the agreement statistic to the number of
raters and data type. Those sources support transparent analysis, not a claim
that these cutoffs establish validity.

## Validity gates after reliability

1. Expert content review of dimensions, weights, and routing.
2. Response-process review of how raters interpret the rubric.
3. Relations-to-criteria study against predeclared expert or outcome measures.
4. Fairness/slice analysis across project type, language, access, and team size.
5. Consequence study showing that use of the report improves decisions without
   exceeding its evidence limits.

Primary references: [AERA/APA/NCME Standards](https://www.apa.org/science/programs/testing/standards?clearcache=true),
[Koo and Li](https://pubmed.ncbi.nlm.nih.gov/27330520/), and
[Hallgren](https://pmc.ncbi.nlm.nih.gov/articles/PMC3402032/).
