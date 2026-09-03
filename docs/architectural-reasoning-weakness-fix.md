# Architectural-reasoning compactness fix

## Observed weakness

The v1.3.1 candidate told the target model to keep a Quick decision below 300
words, yet its preserved behavioral transcript used 499 words. The optimizer
still assigned utility `1.0` because its scorer checked only whether seven
phrases occurred in the skill text. It measured the presence of an instruction,
not compliance with that instruction.

This is a proxy failure, not evidence that the word limit is wrong. The
pre-registered scenario already provides the outcome-level test:
`01-stop-when-supported` requires `max_words: 300`.

## Research basis

- [OPRO](https://arxiv.org/abs/2309.03409) generates candidate instructions and
  evaluates each solution by its task objective. This supports keeping proposal
  generation separate from outcome measurement; prompt wording cannot score
  itself.
- [Instruction-Following Evaluation for Large Language Models
  (IFEval)](https://arxiv.org/abs/2311.07911) builds evaluation around
  mechanically verifiable constraints. This supports translating “be compact”
  into observable word, section, and item limits.
- [EvoPrompt](https://arxiv.org/abs/2309.08532) applies evolutionary search with
  task fitness. This supports using structural checks as a cheap filter while
  reserving selection claims for executed fitness cases.
- [DSPy](https://arxiv.org/abs/2310.03714) optimizes LM programs against declared
  metrics. This supports treating the scenario metric as part of the program,
  rather than relying on subjective inspection of the compiled prompt.

These papers do not establish that one particular compactness instruction will
work for every model. They justify the evaluation design: observable contracts,
executed outcomes, and held-out disposal.

## Implemented correction

The v1.3.2 proposal replaces the loose budget paragraph with a completion
contract that is easier to execute and verify:

1. exactly four ordered sections;
2. at most two bullets per section and one claim per bullet;
3. a hard 300-word response cap with a pre-send compression check;
4. no preamble or completeness-oriented appendices;
5. explicit stop and safety-escape rules.

The structural scorer now checks all of those relationships, not isolated
phrases. Its output explicitly records:

```json
{
  "evidence_tier": "structural_proxy",
  "behavioral_validation_required": true,
  "validated_claim": "instruction_contract_present",
  "unsupported_claim": "target_model_obeys_contract"
}
```

A candidate is behaviorally supported only after the target model executes the
held-out scenario suite through `--executor-fn` and the resulting transcript
passes the scenario's `success_band`. Multiple rollouts are required before a
reliability claim; a single pass is only a successful pilot.
