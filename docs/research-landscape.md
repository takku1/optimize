> **2026-08-29**: The formal framework this notes file was building toward —
> capability contracts, task taxonomy, evaluator stack, search loop, maturity
> tiers — now lives in `docs/bcso-bench.md`. This file remains
> as the literature survey and the informal reasoning trail that led there;
> where a section below has been superseded by a formalized, implemented
> version, it says so and points at the spec instead of repeating it.

# Research landscape

## The question

Given a desired behavior change in an LLM, is there a formalized discipline for finding the *specific, minimal wording* that reliably produces it — not just "make the prompt shorter," but "which words do the most behavioral work per token, and why"?

Origin: came up while iterating on the `architectural-reasoning` Claude Skill (`Z:\archetect\skills\architectural-reasoning`), where short, specific phrases ("distrust the prior summary," "authoritative owner," "re-verify each prior finding") repeatedly outperformed longer explanatory wording across several rounds of multi-reviewer critique. See that repo's git history (v1.0 → v1.2.4) for the working case study.

## Three real fields, no single unifying name

No field currently names the full composite ("search discrete wording that maximizes desired latent-concept activation per token while minimizing irrelevant activation, evaluated by behavioral reliability"). But three adjacent, actively-researched fields each answer part of it:

### 1. Discrete prompt optimization / Automatic Prompt Engineering (APE)

**Closest match to the actual question.** Treats candidate phrasings as a search space, scores them against a task/objective, keeps the winner.

- **OPRO** — Yang et al., 2023, ["Large Language Models as Optimizers"](https://arxiv.org/abs/2309.03409). The single closest hit: this is the paper that discovered "Take a deep breath and work through this step by step" outperforms longer instructions on math tasks — a short phrase with outsized behavioral effect, found by iterative search.
- **APE** — Zhou et al., 2022, "Automatic Prompt Engineer." Feeds an optimizer LLM a meta-prompt (goal description + history of prior candidates + scores), asks it to propose better candidates, iterates.
- **AutoPrompt** — Shin et al., 2020. Earlier, token-level (gradient/enumeration-based) approach to finding prompts that trigger latent model knowledge.
- **Promptbreeder** — Fernando et al., 2023. Evolutionary variant: prompts mutate and compete.

Research paradigm, in general: *generate-and-search* (many candidates, rank/select) vs. *meta-prompting* (a higher-order prompt that generates or improves prompts).

### 2. Prompt compression

**Answers a different question: shrink existing text while preserving quality**, not search for the best short phrase from scratch.

- **LLMLingua** — Microsoft, EMNLP'23/ACL'24. Up to 20x token reduction with minimal performance loss, via a three-stage coarse-to-fine token-importance estimation + budget control.
- **LongLLMLingua**, **LLMLingua-2** — extensions for long-context and token-classification-based compression.

Useful for RAG/context-window budgeting; not directly useful for "what should I write from scratch."

### 3. Representation engineering / activation steering

**The mechanistic explanation for *why* short phrases can have outsized effect** — not itself a technique for authoring prompts.

- **Linear Representation Hypothesis**: high-level concepts are represented (at least approximately) as directions in a model's activation space. Recent work complicates this — concept directions can span multi-dimensional subspaces, with geometry that depends on context and layer depth.
- **Contrastive Activation Addition**, **Inference-Time Intervention**: construct steering vectors from paired (positive/negative) examples, then add them directly to hidden states at inference time. This is a mechanistic intervention on activations, not a prompt-wording technique — different tool, adjacent intuition.
- Survey: ["Representation Engineering for Large-Language Models"](https://arxiv.org/pdf/2502.17601), 2025.

### Related but distinct: in-context learning as implicit Bayesian inference

Xie et al., 2022, ["An Explanation of In-Context Learning as Implicit Bayesian Inference"](https://arxiv.org/abs/2111.02080). Frames a prompt as conditioning evidence that narrows the model's effective output distribution — theoretical grounding for why *specificity* in wording reduces behavioral variance, independent of the search-for-wording question above.

## Naming pitfall — do not reuse "Latent Semantic Optimization"

Checked directly: **"Latent Semantic Optimization" (LSO) is already an established term**, and it means something unrelated — SEO / content-marketing practice of stuffing web copy with topically-related keywords, derived from Latent Semantic Indexing ([Ryte Wiki](https://en.ryte.com/wiki/Latent_Semantic_Optimization/), [Textbroker glossary](https://www.textbroker.com/latent-semantic-optimization)). Reusing this name here would collide with a decade of unrelated existing usage. Prefer the real field name (**discrete prompt optimization**) or a plain, non-colliding informal label (**instruction density**) instead of inventing new jargon.

## Practical takeaway (already validated, not hypothetical)

The `architectural-reasoning` skill's v1.0 → v1.2.4 revision history *is* a manual, human-in-the-loop instance of the OPRO/APE search loop: propose a candidate wording → get independent critique (multiple AI reviewers) → check candidate claims against the actual file (verify, don't trust the reviewer) → keep or revert based on evidence of an actual behavioral gap, not a theoretical one. No new terminology is needed to describe this — it's discrete prompt optimization, done by hand, with an explicit evidence bar (see `Z--archetect` memory: `feedback-evidence-bar-for-skill-edits`) standing in for the automated scoring function that OPRO/APE use algorithmically.

## Expanded PhD-level research map (2026-08-28)

The strongest defensible framing is a multi-objective, black-box optimization problem over discrete sequences, with optional mechanistic measurements. “Instruction density” is a proposed metric, not an established field or validated universal quantity.

### Search and optimization

- AutoPrompt (Shin et al., 2020) uses gradient-guided trigger-token search: https://arxiv.org/abs/2010.15980.
- APE (Zhou et al., 2022) uses LLM-generated candidates plus empirical scoring: https://arxiv.org/abs/2211.01910.
- OPRO (Yang et al., 2023) iterates over prompt histories and scores: https://arxiv.org/abs/2309.03409. Replication work finds strong dependence on optimizer/scorer scale and human-written meta-instructions: https://arxiv.org/abs/2405.10276.
- ProTeGi (Prye et al., 2023) uses textual gradients and beam search: https://arxiv.org/abs/2305.03495.
- Promptbreeder (Fernando et al., 2023) evolves task prompts and mutation prompts: https://arxiv.org/abs/2309.16797.
- EvoPrompt (Guo et al., 2024) studies evolutionary operators for prompt search: https://arxiv.org/abs/2309.08532.
- DSPy (Khattab et al., 2023/2024) compiles declarative LM programs into optimized prompts/demonstrations: https://arxiv.org/abs/2310.03714.
- TextGrad (Yuksekgonul et al., 2024) propagates textual feedback through a computation graph: https://arxiv.org/abs/2406.07496.
- LatentPrompt (2025) searches continuous prompt embeddings, decodes candidates, and scores them: https://arxiv.org/abs/2508.02452. It is the closest machinery to the “roads through latent space” analogy, but does not establish maximum mechanistic activation per token.

### Compression and information

- LLMLingua (Jiang et al., 2023) estimates token importance and compresses existing prompts: https://arxiv.org/abs/2310.05736.
- LongLLMLingua: https://arxiv.org/abs/2310.06839; LLMLingua-2: https://arxiv.org/abs/2403.12968. These motivate joint reporting of quality, latency, and token cost.
- A testable information-theoretic analogue is conditional mutual information (I(Y;w\\mid X)): whether wording (w) reduces uncertainty about behavior (Y), given task/context (X). This is a measurement proposal, not evidence that an activation vector equals semantic information.

### Mechanistic evidence

- ROME demonstrates causal editing/mediation of internal representations: https://arxiv.org/abs/2202.05262.
- Activation Addition and Inference-Time Intervention steer behavior by adding vectors at selected layers: https://arxiv.org/abs/2308.10248 and https://arxiv.org/abs/2306.03341.
- Representation Engineering (Zou et al., 2023) extracts and manipulates concept-associated representations: https://arxiv.org/abs/2310.01405; survey: https://arxiv.org/abs/2502.17601.
- Contrastive Activation Addition builds directions from positive/negative pairs: https://arxiv.org/abs/2312.06681. Candidate wording should therefore be compared by causal change in a probe/subspace, not only cosine distance to one vector.
- Superposition and polysemanticity mean one phrase need not map to one feature. Strong claims require layer-wise ablations/patching, held-out prompts, and preregistered probes.

### Reliability and evaluation

- Instruction Hierarchy shows that priority among system/developer/user text is itself learned behavior: https://arxiv.org/abs/2404.13208.
- Prompt-injection benchmarks show that instruction-following can fail under conflicting embedded text: https://arxiv.org/abs/2308.10819. “Off-target” should include unauthorized or unsafe behavior, not only semantic competitors.
- Report bootstrap intervals, paired baseline tests, multiple seeds, held-out tasks, and a Pareto frontier over quality, tokens, latency, variance, and safety. Separate optimizer and evaluator models/data to reduce leakage.

### Operational definition and falsification

For fixed model (M), context distribution (X), target behavior (Y^*), and wording (w):

$$\\operatorname{ID}(w)=\\frac{\\Delta \\operatorname{Perf}(M,X,Y^*\\mid w)}{\\operatorname{tokens}(w)}$$

Use behavior as the primary measure and activations (A_\\ell(w)) as explanatory evidence:

$$J(w)=\\operatorname{Perf}(w)-\\lambda\\,\\operatorname{tokens}(w)-\\beta\\,\\operatorname{risk}(w)-\\gamma\\,\\operatorname{variance}(w).$$

The “White House avenue” hypothesis is falsified if a short phrase’s effect disappears on held-out tasks/models, under paraphrase or position changes, or with a blinded evaluator.

## Prototype validation status

The original `tests/test1.py`–`test3.py` were executable notebooks split across files: definition-order dependencies, a hard-coded `/mnt/agents/output` path, plot display during collection, global RNG state, and no assertions made them unsuitable as tests. They are now deterministic pytest modules backed by `tests/simulation.py`, covering normalization, reproducibility, token penalties, bounds, and zero-token handling. These validate implementation invariants only; they do not validate the latent-space theory or any real-LLM ranking.

Next milestone: preregister a candidate set, evaluate paired outputs on held-out tasks across at least two model families, and report the full Pareto frontier before fitting an activation probe.

## Grounding for BCSO-Bench's own methodology (2026-09-03)

The sections above ground the *search-for-wording* question. This section
grounds a different, previously uncited part of the design: why
`contracts.compare_contract_results` gates on an absolute hard-invariant floor
rather than a single blended score, why the empirical pilot used blinded
per-transcript judging, and why paired comparison uses a bootstrap
non-inferiority margin instead of a plain score delta. These are the design
choices STATUS.md and the benchmark card describe but had not previously
connected to the literatures they most resemble.

### Hard, absolute constraints vs. a blended objective

`HardInvariant.min_pass_rate` and `compare_contract_results`'s policy — a
candidate is `accepted` only if *every* declared invariant clears its own
floor, independent of how much utility it gains elsewhere — is the same shape
of problem as constrained (safe) reinforcement learning: optimize a scalar
objective subject to constraints that must hold on their own terms, not be
traded off against reward. Recent safe-RL work is directly relevant to two
open questions this project has not yet resolved:

- **State-wise (per-unit) vs. expectation constraints.** This project already
  requires the floor to hold per invariant across all rollouts of a unit
  (`aggregate_rollout_results`, added 2026-09-03), which is closer to a
  state-wise guarantee than an average-case one. "Absolute State-wise
  Constrained Policy Optimization" formalizes exactly this distinction —
  high-probability *state-wise* constraint satisfaction, not just satisfaction
  in expectation — and is the closest published framing to what
  `min_pass_rate=1.0` is already doing:
  https://arxiv.org/pdf/2410.01212
- **Constraint sensitivity / how strict a floor should be.** "CSPO:
  Constraint-Sensitive Policy Optimization for Safe Reinforcement Learning"
  and "A Survey of Constraint Formulations in Safe Reinforcement Learning"
  cover the design space between hard (never-violate) and soft (rarely-violate,
  penalized) constraints — relevant to the open question this project's own
  empirical pilot surfaced (`REPORT.md`'s "Absolute-vs-relative invariant
  gating is a real open design question"): should a floor be judged against
  an absolute bar, a relative regression from baseline, or a tolerance band.
  https://arxiv.org/pdf/2606.14415 ,
  https://arxiv.org/pdf/2402.02025

These are process-safety RL papers, not prompt-evaluation papers — the
transfer is structural (absolute per-unit constraint satisfaction under a
scalar objective), not a claim that this project uses RL. No published work
found applies this framing to natural-language skill/prompt evaluation
specifically; that combination remains this project's own contribution, not
one lifted from a citation.

### Blinded LLM-as-judge scoring

The empirical pilot's blinding design (opaque ids generated before judging,
version identity never in a judge prompt, a fresh judge agent per transcript)
anticipates a documented failure mode in the LLM-as-judge literature: judges
are measurably unreliable without calibration, and the standard practice is to
validate a judge against a human-labeled sample before trusting it at scale.

- "Reliability without Validity: A Systematic, Large-Scale Evaluation of
  LLM-as-a-Judge Models Across Agreement, Consistency, and Bias" is the most
  direct warning that a judge can be internally consistent while still
  disagreeing with human ground truth:
  https://arxiv.org/pdf/2606.19544
- The standard calibration recipe — sample 100-300 labeled traces, get 2-3
  human annotators, compute inter-annotator agreement (Cohen's kappa; ~0.6
  acceptable, ~0.8 strong), then compare judge-to-human agreement on the same
  traces — is exactly what `docs/STATUS.md`'s "Human/judge agreement has not
  been calibrated on a representative labeled set" is naming as *not yet
  done*, and exactly what should close that gap when it is. Domain-specific
  judge/human agreement has been reported as low as 60-68% in some fields,
  which is the concrete reason this project should not assume its own judge
  is reliable without measuring it directly, on its own scenarios.
- "Trust or Escalate: LLM Judges with Provable Guarantees for Human
  Agreement" (ICLR 2025) frames judge reliability as something that should
  come with a guarantee, not an assumption — a stronger bar than this
  project currently meets:
  https://proceedings.iclr.cc/paper_files/paper/2025/file/08dabd5345b37fffcbe335bd578b15a0-Paper-Conference.pdf

### Paired non-inferiority testing

`compare_contract_results`'s `noninferiority_margin` and bootstrap delta
interval borrow the shape of a non-inferiority test (does the candidate's
lower confidence bound stay above `-margin`, not just "is the mean better"),
which is standard in paired diagnostic-accuracy comparisons:

- Non-inferiority/equivalence testing on paired diagnostic accuracy measures
  (matching this project's paired baseline/candidate design) is a mature
  clinical-statistics area; two-one-sided-tests (TOST) and paired-AUC
  approaches are the closest classical precedent:
  https://pubmed.ncbi.nlm.nih.gov/16158400/ ,
  https://www.tandfonline.com/doi/full/10.1080/19466315.2024.2402276
- For binary paired outcomes specifically (closer to this project's per-
  invariant pass/fail than to a continuous score), McNemar's-test-based paired
  comparison is the standard alternative worth checking the current bootstrap
  approach against:
  https://pubmed.ncbi.nlm.nih.gov/11782062/

None of this changes the project's actual numbers — it's a citation pass, not
a re-analysis. What it does is give three previously-uncited design choices
(absolute per-unit hard floors, blinded per-transcript judging, bootstrap
non-inferiority) a named literature to be checked against, and names the gap
precisely: this project runs the *shape* of judge calibration and non-
inferiority testing that these fields consider baseline practice, but has not
yet done the specific calibration step (human-labeled sample, kappa,
judge-to-human agreement) that would let it claim its judge is trustworthy
rather than merely blinded.

## Open questions / backlog

## Rate-distortion framing (verified)

The proposed rate-distortion analogy is stronger than a raw activation-per-token score when the task is explicitly compression: minimize token rate subject to an acceptable behavioral distortion. Girish et al. formalize hard prompt compression for black-box LLMs, derive a distortion-rate function as a linear program, and show that query-aware, variable-rate compression matters ([paper](https://arxiv.org/abs/2407.15504), [ICML project](https://icml.cc/virtual/2024/37849)). This directly supports using an empirical lower envelope of distortion at each token budget in the prototype.

The analogy has limits: Shannon rate-distortion assumes a source distribution and a specified distortion measure; an LLM prompt is an intervention whose effect depends on model, query, position, decoding, and safety constraints. Therefore `distortion = 1 - reliability` is only a toy proxy until a task-specific behavioral distortion is defined. The Information Bottleneck formulation is a complementary perspective: compress the intended instruction while preserving information relevant to the target behavior ([Tishby, Pereira & Bialek](https://arxiv.org/abs/physics/0004057)).

The source now exposes `rate_distortion_frontier()`, which reports the best observed distortion at each token rate. It is an empirical frontier, not Shannon's theoretical bound. A future real-model study should estimate confidence intervals around each point and compare against query-aware compression baselines.

## Additional mathematically grounded improvements (primary sources)

- **PAC-Bayes model selection:** Akinwande et al. show that a language-model prior plus a discrete prompt can yield useful generalization bounds and can rank prompts for model selection ([paper](https://arxiv.org/abs/2310.03957)). Practical implication: penalize candidate complexity relative to a fixed prior instead of trusting optimization-set performance alone.
- **Bayesian optimization over discrete prompts:** Sabbatella et al. formulate hard prompt tuning as combinatorial optimization and search a continuous embedding surrogate ([paper](https://arxiv.org/abs/2312.00471)). This is a sample-efficient alternative to PPO when each model evaluation is expensive.
- **Bayesian posterior sampling:** BayesPO treats prompts as posterior samples with a language-model prior and task-likelihood term, while warning about overfitting and compute cost ([paper](https://arxiv.org/abs/2607.16001)). Use this as a research option, not as evidence that posterior sampling is universally superior.
- **Active learning:** choose the next task/candidate where the current frontier is most uncertain or where two candidates are likely to exchange dominance. This reduces expensive labeling compared with uniform evaluation; uncertainty must be estimated from repeated measurements or a calibrated surrogate.
- **Causal estimands:** define the treatment as “insert wording (w) at position (j)” and estimate the paired average treatment effect against the same baseline task. This separates wording effects from task composition and position confounds.
- **Counterfactual generalization:** evaluate on rule- or domain-shifted tasks, not only held-out examples from the same template. Counterfactual-evaluation work shows that apparent reasoning performance can rely on default-condition shortcuts ([paper](https://arxiv.org/abs/2307.02477)).

The prototype now includes `bootstrap_mean_interval()` for reproducible non-parametric uncertainty intervals. These intervals are only useful once values come from real repeated model measurements; they do not turn the synthetic simulator into empirical evidence.

## Intent-preserving transformation (superseded — see bcso-bench.md)

This section's original content (a versioned `IntentContract`, paired `compare` command,
constrained multi-objective formulation) is now formalized as part of the Γ capability
contract and the search loop's objective space — see `docs/bcso-bench.md`
§1 and §3. `IntentContract` and `compare_contract_results` remain unchanged and
implemented in `prompt_optimization.contracts`; reviewed seed contracts and scenarios are
still in `tests/fixtures/contracts/` and `tests/fixtures/scenarios/`.

## Attribution and direction layer (implemented; ablation reuse noted in bcso-bench.md §12)

The prototype now keeps attribution separate from compression objectives. `shapley_values()` estimates average marginal contribution over component coalitions (exact permutation enumeration for small prompts, reproducible Monte Carlo permutations for larger prompts); `interaction_effect()` computes the second-order inclusion-exclusion synergy/interference term; `causal_deletion_effect()` names the paired deletion estimand; and `directional_projection()` reports projection of an observed state/embedding change onto a declared target direction. These are estimators and diagnostics, not mechanistic proof. For closed systems such as Midjourney, use output-level interventions and do not imply access to hidden activations. The Midjourney-specific protocol is documented in `output/midjourney-research-review.md`.

- Is there value in formalizing the manual process above into a reusable checklist or companion skill (e.g., "before merging a wording change to any Skill/prompt, run it through: does this collide with an existing anchored term elsewhere in the document? is the claim behind it verified against the file, not just plausible? is there an observed failure, or only a theoretical one?")? Not started — evaluate after this notes phase is more complete.
- Could a lightweight version of OPRO's iterate-and-score loop be run programmatically (not by hand) against Claude Skills specifically, using real usage transcripts as the scoring signal? Speculative; no evidence yet this is worth building.
- No action taken on either yet — this file is research notes, not a design doc for a specific deliverable.
