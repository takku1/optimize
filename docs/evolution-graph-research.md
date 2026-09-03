# Evolution graph research grounding

Last verified: 2026-08-29. This grounds the 50-section "Skill Evolution Graph +
Neural Optimizer" proposal against real, citable research and existing
systems, in the same spirit as `docs/research-landscape.md`: state
what's established precedent, what's speculative, and where the proposal's
own confident tone claims more than the literature currently supports.
Cross-referenced against what this repo already implements, so the
recommendation at the end is concrete, not just critique.

## Headline finding: this has substantially already been built, for code

The single closest real system is DeepMind's **FunSearch**
(Romera-Paredes et al., *Nature* 2023/2024, "Mathematical discoveries from
program search with large language models") and its successor
**AlphaEvolve** (Novikov et al., Google DeepMind, 2025). Both maintain an
evolutionary **program database** — every candidate program, its lineage,
and its evaluator score, kept rather than overwritten — and use an LLM as
the mutation operator, prompted with retrieved high-scoring ancestors from
that database, with island-based/Pareto-style selection deciding what
survives. That is: content-addressed lineage graph + real evaluator +
retrieval-conditioned LLM mutation + multi-objective selection, exactly the
shape of sections 1-10 and 15-18 of the proposal — already running in
production, just for code instead of natural-language skills.

**The important correction this precedent supplies**: neither FunSearch nor
AlphaEvolve trains a dedicated neural network to predict, rank, or generate
mutations (the proposal's sections 11-14, 44 stages 1-4). Both use
**retrieval + in-context LLM prompting** over the lineage database as the
"learned" component — the LLM itself, not a gradient-trained checkpoint, is
the mutation generator, world model, and ranker rolled into one, conditioned
by what's retrieved. This repo's existing `search.loop._default_diagnose`
(a heuristic "pick whichever operator most recently won" — see
`docs/bcso-bench.md` §10) and its documented pluggable
`diagnose_fn` are already positioned to become exactly this: retrieval over a
real lineage store feeding an LLM call, with no new model training required.
The proposal's Stage 1-4 neural checkpoints (world model, ranker, generator)
are a genuinely further step than any published system in this space has
taken — worth attempting eventually, but they are the most speculative part
of the document, not (as the confident tone might suggest) an established
technique being applied to a new domain.

## Section-by-section grounding

### Immutable, content-addressed provenance (§§3-8, 42-43)

Solid engineering precedent, correctly reasoned in the source document
itself: this is Git's object model (content-addressed blobs, a Merkle DAG of
commits) plus what ML experiment-lineage tools already do in practice —
MLflow, DVC, and Weights & Biases artifact lineage all hash-address
artifacts and record parent/child relationships without any blockchain
machinery. Merkle trees themselves trace to Merkle (1988), *A Digital
Signature Based on a Conventional Encryption Function*, CRYPTO '87. The
proposal's own §8 ("no mining, no consensus, no tokens needed") is the
correct read — cite it as confirmed, not as a novel insight to prove.
**What's missing from this repo today**: `capability.provenance.content_hash`
exists, and `search.population.Candidate` already carries `parent_ids`/
`mutation_type` lineage, but neither is persisted to an actual
content-addressed store (`skills/<hash>.md`, `mutations/<id>.json`, ...) —
this is real, small, buildable work, not research.

### Independent benchmark, calibration/optimization corpus separation, sealed test (§§9-10, 27, 30-31)

Already the operating model of this project (`docs/bcso-bench.md`
§2's five-way split, `docs/governance.md`'s status-tag convention).
Grounded the same way this repo already grounds it: MLPerf's rules/audit
discipline, Dynabench's dynamic-benchmark-regeneration motivation, and the
benchmark-contamination survey already cited in
`docs/research-landscape.md` (arXiv:2406.04244). The proposal adds
nothing beyond what's already documented here — good, it means this part of
the vision is already load-bearing in running code, not aspirational.

### "World model" outcome prediction (§§11-12)

The proposal's own citation instinct (Ha & Schmidhuber, *World Models*,
arXiv:1803.10122) is the wrong nearest neighbor — that line of work predicts
raw sensory dynamics (pixels) for a controller to plan against. Predicting a
scalar behavioral-delta vector from *(current text, proposed edit)* is
structurally much closer to **performance prediction in neural architecture
search** — e.g. White et al. 2021, *How Powerful are Performance
Predictors in Neural Architecture Search?* (arXiv:2104.01177) — where a
cheap learned surrogate reduces how often the expensive real evaluator has
to run. That reframing matters: NAS performance predictors are known to
degrade sharply on architectures unlike anything in their training set, and
the same risk applies directly to §12's "world model" once a mutation family
or skill family is out-of-distribution relative to the graph so far — the
proposal should inherit NAS's discipline of reporting predictor calibration
error, not just claiming search-cost savings.

### Learned mutation ranker (§13)

Real, tractable precedent: pairwise preference learning under the
Bradley-Terry model, as used directly in RLHF reward modeling (Christiano
et al. 2017, *Deep Reinforcement Learning from Human Preferences*,
arXiv:1706.03741). The modern, lighter-weight version of exactly this
setup — train directly on preference pairs without a separate reward model
or RL loop — is **Direct Preference Optimization** (Rafailov et al. 2023,
arXiv:2305.18290). Given §13's own training examples are already
naturally-occurring pairwise preferences ("candidate A preferred over
candidate B"), DPO-style training is a more direct fit than the RL stages
proposed later in §44, and doesn't require the reward-model/policy
machinery those stages assume.

### Learned mutation generator (§14) and RL stages (§§24-26, 44 stages 5-6)

As noted above, no published comparable system trains a dedicated generator
checkpoint — this project's own already-cited prompt-evolution literature
(Promptbreeder, EvoPrompt, GEPA — see `docs/research-landscape.md`)
all use an LLM prompted with history, not a trained model. For the RL stages
specifically: **offline RL's central known failure mode is extrapolation
error on actions unlike anything in the training distribution**
(Levine, Kumar, Tucker, Fu 2020, *Offline Reinforcement Learning: Tutorial,
Review, and Perspectives on Open Problems*, arXiv:2005.01643) — directly
relevant to §25's "learn from historical trajectories first," since a policy
trained offline on this project's own transition graph will be systematically
overconfident about mutation families rarely tried. If RL is pursued, ground
the objective in **constrained MDPs** (Altman 1999) via a method like
**Constrained Policy Optimization** (Achiam, Held, Tamar, Abbeel 2017,
arXiv:1705.10528) rather than a scalarized reward — this matches §26's own
instinct ("avoid `r = U/L`... use constrained objectives") and gives it a
concrete algorithm rather than a design principle alone.

### Reward hacking / evaluator-gaming defenses (§27)

Correctly identified as necessary; well-grounded in the literature. Amodei
et al. 2016, *Concrete Problems in AI Safety* (arXiv:1606.06565) names
reward hacking as a fundamental risk category; Skalse, Howe,
Krasheninnikov, Krueger 2022, *Defining and Characterizing Reward Hacking*
(arXiv:2209.13085) formalizes when it's provably unavoidable; and — the most
directly actionable citation for this proposal — Gao, Schulman, Hilton 2022,
*Scaling Laws for Reward Model Overoptimization* (arXiv:2210.10760) shows
empirically that optimizing *against a learned proxy* for quality gets
*worse*, not better, the harder you optimize, past a point. That's a direct
empirical argument for §27's hidden-audit-suite design (the optimizer must
never see individual hidden-test answers) and for this project's own
existing `evaluators.calibration.EVALUATOR_UNSTABLE` flag — both are the
right shape of defense per this literature.

### Component attribution (§§32, 34)

Already implemented in this repo (`attribution/shapley.py`,
`contracts.ablation_deltas`), grounded in cooperative game theory (Shapley
1953) and its ML popularization (Lundberg & Lee 2017, *A Unified Approach to
Interpreting Model Predictions* / SHAP, arXiv:1705.07874). Worth adding as a
comparison point: **influence functions** (Koh & Liang 2017, *Understanding
Black-box Predictions via Influence Functions*, arXiv:1703.04730) attribute
outcome changes to training data rather than input components, which is a
different question (why did the *model* behave this way, not why did the
*prompt component* matter) — not a substitute, but worth citing so "component
attribution" doesn't get conflated with the adjacent but distinct data-
attribution literature.

### Latent skill-space / edit vectors (§§19-21)

The proposal's most under-cited and most directly precedented idea.
Yin, Neubig, Allamanis, Brockschmidt, Gaunt 2018, *Learning to Represent
Edits* (arXiv:1810.13337, ICLR 2019) trains exactly `Δz = z_after - z_before`
representations of code edits and shows they cluster by edit type — this is
the paper to read before building §19-21, not a from-scratch idea. One
hedge worth carrying over: the "recurring directions" framing (§19's
example: "activation precision ↑, redundancy ↓...") echoes the early
word2vec king-queen-style analogy claims, which later work showed are less
robust and more basis-dependent than first reported — treat any discovered
"direction" as a hypothesis requiring the same held-out behavioral
validation as any other mutation, not as free knowledge once found.

### Retrieval of historical analogues (§16)

Two real precedents, one much older than the other: **case-based reasoning**
(Aamodt & Plaza 1994, *Case-Based Reasoning: Foundational Issues,
Methodological Variations, and System Approaches*) is the 30-years-earlier,
non-neural version of exactly §16's proposal (retrieve similar past cases,
adapt the solution, learn from the outcome) and is arguably the more precise
conceptual ancestor than RAG (Lewis et al. 2020,
*Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*,
arXiv:2005.11401), which is the modern neural retrieval mechanism for
implementing it. Cite CBR for the framing, RAG for the implementation.

### Graph neural networks over the evolution graph (§§17-18)

The proposal's own hedge ("should not be assumed necessary... transformers
over serialized histories may work perfectly well") is well-calibrated and
matches current practice — many recent systems linearize graph-structured
history into sequences for a transformer rather than using a dedicated GNN
(the classic GNN reference, for when one is warranted, is Kipf & Welling
2016, *Semi-Supervised Classification with Graph Convolutional Networks*,
arXiv:1609.02907). No correction needed here; this is the one place the
source document's own uncertainty is already the right amount.

### Cross-model mutation transfer (§§36-37)

Genuinely open. There is real work studying whether optimized prompts
transfer across model families, generally finding transfer is partial and
sometimes fails in the discrete-prompt setting even when it succeeds for
soft/continuous prompts — this repo already frames the honest version of
this question via `evaluators.profiles` capability families and the
maturity tier's `cross_model_transfer` gate
(`capability.maturity.classify_maturity`), which requires it be *measured*,
not assumed. Nothing in §§36-37 should be treated as established; it's
correctly scoped in this repo as a `PORTABLE` maturity gate that has to be
earned, not inferred from single-model results.

## What this means for what to build next

The grounding supports the proposal's own §49 ("the next practical asset is
simply a high-quality immutable transition dataset") more strongly than it
supports jumping to §§11-14/44's neural layers — and it changes *how* to
build the eventual "learned" layer once the dataset exists: retrieval +
in-context LLM prompting (matching FunSearch/AlphaEvolve/GEPA/Promptbreeder,
all of which this project already cites) before a trained predictor/ranker/
generator checkpoint, and DPO-style preference training on the ranker's
naturally-occurring pairwise data (§13) before full offline RL (§§25-26) if
a trained component is attempted at all.

Concretely, against what already exists in this repo:

- **Already implemented, matches the proposal**: Pareto/hypervolume archive
  (`search.archive` ≈ §21's multi-objective layer), promotion states
  (`capability.promotion.PromotionVerdict` ≈ §22's CANDIDATE/
  VALIDATED_IMPROVEMENT/REJECTED, though §22 wants more intermediate states
  — GENERATED/EXECUTED/MEASURED — than this repo currently distinguishes),
  component attribution (`attribution.shapley` ≈ §34), lineage-on-Candidate
  (`search.population.Candidate.parent_ids` ≈ the DAG edges in §5),
  provenance record (`capability.provenance.ProvenanceRecord` ≈ most of §7's
  `EvaluationRecord` fields).
- **Real, small, next step**: persist that lineage to an actual
  content-addressed store (§4, §42) — a database plus hashed object files,
  no new research needed, matches the empirical-evaluator work just
  completed in `output/claude skills/architectural-reasoning/
  empirical-run-2026-08-29/`, which already produced exactly this shape of
  record by hand.
- **Not yet grounded enough to build**: any of the trained-checkpoint stages
  (§44 stages 1-6). Per the FunSearch/AlphaEvolve precedent, get retrieval +
  in-context proposal working over a real lineage store first; only escalate
  to a trained model if that retrieval-based approach demonstrably plateaus
  — which is also just the proposal's own §40/§41 exploration discipline
  applied one level up, to the decision of whether to train a model at all.
