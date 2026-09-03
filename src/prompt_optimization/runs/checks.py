"""Deterministic, mechanical checks over experiment transcripts.

This replaces the per-run ``deterministic_checks.py`` one-off scripts. Given the
same transcripts and the same declarative check rules it produces exactly the
same JSON every time (requirement: evaluate deterministic criteria
deterministically), with no Python authoring per run and no host-specific path
assumptions.

Rule language
-------------
A ``checks`` stage in the run manifest declares ``versions``, ``scenarios``, a
``transcript_pattern`` (``{version}``/``{scenario}`` are substituted), and a
``units`` mapping from scenario id to a list of rules. When the rule has no
``scenarios`` filter it applies to every scenario.

Each rule produces one named field on the entry:

* ``{"field": f, "op": "word_count"}`` -> ``len(text.split())``
* ``{"field": f, "op": "mentions_any", "phrases": [...], "casefold": true}`` -> bool
* ``{"field": f, "op": "count_word", "word": "...", "casefold": true}`` -> int (word-boundary count)
* ``{"field": f, "op": "derived", "expr": "..."}`` -> a constrained boolean/numeric
  expression evaluated over the fields computed so far for this unit.

The ``derived`` expression is parsed by a small recursive-descent parser that
accepts only identifiers, numeric literals, ``True``/``False``, ``and``/``or``/
``not``, and the comparison operators ``<= < > >= == !=``. No function calls,
no attribute access, no indexing, no ``in`` — so arbitrary code cannot be
injected through a manifest.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from .manifest import RunManifest


class CheckExpressionError(ValueError):
    """Raised when a ``derived`` check expression is malformed or unsafe."""


# ---------------------------------------------------------------------------
# Constrained expression evaluator (no eval / exec).
# ---------------------------------------------------------------------------
_TOKEN_RE = re.compile(r"\s*(<=|>=|==|!=|<|>|[()]|[A-Za-z_][A-Za-z0-9_.]*|\d+(?:\.\d+)?)")


def _tokenize(expr: str) -> list[str]:
    tokens: list[str] = []
    pos = 0
    while pos < len(expr):
        match = _TOKEN_RE.match(expr, pos)
        if not match:
            rest = expr[pos:].strip()
            if rest:
                raise CheckExpressionError(f"unexpected token in derived expression: {rest[:20]!r}")
            break
        tokens.append(match.group(1))
        pos = match.end()
    return tokens


class _Evaluator:
    __slots__ = ("tokens", "pos", "env")

    def __init__(self, tokens: list[str], env: Mapping[str, Any]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.env = env

    def _peek(self) -> str | None:
        if self.pos >= len(self.tokens):
            return None
        return self.tokens[self.pos]

    def _eat(self, expected: str) -> None:
        if self._peek() != expected:
            raise CheckExpressionError(f"expected {expected!r}")
        self.pos += 1

    def _atom(self):
        tok = self._peek()
        if tok is None:
            raise CheckExpressionError("unexpected end of expression")
        if tok == "(":
            self.pos += 1
            value = self._or()
            self._eat(")")
            return value
        if tok == "True":
            self.pos += 1
            return True
        if tok == "False":
            self.pos += 1
            return False
        if tok in ("and", "or", "not"):
            raise CheckExpressionError(f"unexpected keyword {tok!r} in operand position")
        if re.match(r"^-?\d", tok) or (tok[0].isdigit() if tok else False):
            self.pos += 1
            return float(tok) if "." in tok else int(tok)
        if re.match(r"^[A-Za-z_]", tok):
            self.pos += 1
            if tok not in self.env:
                raise CheckExpressionError(f"unknown field in derived expression: {tok!r}")
            return self.env[tok]
        raise CheckExpressionError(f"unexpected token: {tok!r}")

    def _comparison(self):
        left = self._atom()
        op = self._peek()
        if op in ("<=", "<", ">", ">=", "==", "!="):
            self.pos += 1
            right = self._atom()
            try:
                if op == "<=":
                    return left <= right
                if op == "<":
                    return left < right
                if op == ">":
                    return left > right
                if op == ">=":
                    return left >= right
                if op == "==":
                    return left == right
                return left != right
            except TypeError as exc:
                raise CheckExpressionError(f"cannot compare {type(left).__name__} {op} {type(right).__name__}") from exc
        return left

    def _not(self):
        if self._peek() == "not":
            self.pos += 1
            value = self._not()
            if not isinstance(value, bool):
                raise CheckExpressionError("'not' requires a boolean operand")
            return not value
        return self._comparison()

    def _and(self):
        value = self._not()
        while self._peek() == "and":
            self.pos += 1
            right = self._not()
            if not isinstance(value, bool) or not isinstance(right, bool):
                raise CheckExpressionError("'and' requires boolean operands")
            value = value and right
        return value

    def _or(self):
        value = self._and()
        while self._peek() == "or":
            self.pos += 1
            right = self._and()
            if not isinstance(value, bool) or not isinstance(right, bool):
                raise CheckExpressionError("'or' requires boolean operands")
            value = value or right
        return value

    def evaluate(self) -> Any:
        value = self._or()
        if self.pos != len(self.tokens):
            raise CheckExpressionError(f"trailing tokens in derived expression: {self.tokens[self.pos:]!r}")
        return value


def eval_derived(expr: str, env: Mapping[str, Any]) -> Any:
    """Evaluate a constrained derived-check expression against ``env``."""
    tokens = _tokenize(expr)
    return _Evaluator(tokens, env).evaluate()


# ---------------------------------------------------------------------------
# Check primitives.
# ---------------------------------------------------------------------------
def _word_count(text: str) -> int:
    return len(text.split())


def _mentions_any(text: str, phrases: tuple[str, ...], *, casefold: bool) -> bool:
    needle = text.casefold() if casefold else text
    return any((phrase.casefold() if casefold else phrase) in needle for phrase in phrases)


def _count_word(text: str, word: str, *, casefold: bool) -> int:
    hay = text.casefold() if casefold else text
    needle = word.casefold() if casefold else word
    return len(re.findall(rf"\b{re.escape(needle)}\b", hay))


def _count_labels(text: str, words: tuple[str, ...], *, casefold: bool) -> int:
    """Count how many of ``words`` appear as word-boundary matches (each once)."""
    hay = text.casefold() if casefold else text
    count = 0
    for word in words:
        needle = word.casefold() if casefold else word
        if re.search(rf"\b{re.escape(needle)}\b", hay):
            count += 1
    return count


def _apply_rule(rule: Mapping[str, Any], text: str, env: dict[str, Any]) -> Any:
    op = rule.get("op")
    field = str(rule.get("field", "")).strip()
    if not field:
        raise ValueError("checks rule requires a non-empty 'field'")
    if op == "word_count":
        value = _word_count(text)
        env[field] = value
        return field, value
    if op == "mentions_any":
        phrases = rule.get("phrases", ())
        if not isinstance(phrases, (list, tuple)) or not phrases:
            raise ValueError(f"rule {field!r}: 'mentions_any' requires a non-empty 'phrases' list")
        value = _mentions_any(text, tuple(phrases), casefold=bool(rule.get("casefold", True)))
        env[field] = value
        return field, value
    if op == "count_word":
        word = str(rule.get("word", "")).strip()
        if not word:
            raise ValueError(f"rule {field!r}: 'count_word' requires 'word'")
        value = _count_word(text, word, casefold=bool(rule.get("casefold", True)))
        env[field] = value
        return field, value
    if op == "count_labels":
        words = rule.get("words", ())
        if not isinstance(words, (list, tuple)) or not words:
            raise ValueError(f"rule {field!r}: 'count_labels' requires a non-empty 'words' list")
        value = _count_labels(text, tuple(words), casefold=bool(rule.get("casefold", True)))
        env[field] = value
        return field, value
    if op == "derived":
        expr = str(rule.get("expr", "")).strip()
        if not expr:
            raise ValueError(f"rule {field!r}: 'derived' requires 'expr'")
        value = eval_derived(expr, env)
        if not isinstance(value, bool):
            raise ValueError(f"rule {field!r}: 'derived' expression must yield a boolean")
        env[field] = value
        return field, value
    raise ValueError(f"unknown checks rule op: {op!r}")


# ---------------------------------------------------------------------------
# CSV-style missing-transcript handling and the stage driver.
# ---------------------------------------------------------------------------
def run_checks(manifest: RunManifest) -> dict[str, dict[str, Any]]:
    """Execute the manifest's ``checks`` stage and return the results mapping.

    With the default single-element ``rollouts`` (``["rollout_01"]``), results
    are keyed ``"{version}:{scenario}"`` (the legacy, K=1 output layout) for
    exact backward compatibility. Declaring more than one rollout switches the
    key to ``"{version}:{scenario}:{rollout}"`` for every entry, so a K>1 run
    never silently collapses distinct rollouts onto one shared check result.
    Transcripts that are missing are skipped with a note recorded in the
    returned object's ``meta`` (never a crash). Paths come from the
    manifest's ``paths``: ``transcripts_dir`` (directory) plus a ``checks``
    pattern defaulting to ``{version}/{scenario}/{rollout}.md``.
    """
    opts = manifest.stage("checks")
    versions = [str(v) for v in opts.get("versions", ())]
    scenarios = [str(s) for s in opts.get("scenarios", ())]
    if not versions or not scenarios:
        raise ValueError("checks stage requires non-empty 'versions' and 'scenarios'")
    rollouts = [str(r) for r in opts.get("rollouts", ("rollout_01",))]
    if not rollouts:
        raise ValueError("checks stage 'rollouts' must not be empty when declared")
    single_rollout = len(rollouts) == 1

    transcripts_dir = manifest.resolve("transcripts_dir")
    pattern = str(opts.get("transcript_pattern", "{version}/{scenario}/{rollout}.md"))
    units = opts.get("units", {})
    if isinstance(units, Mapping):
        # Always run the default rule set for every scenario unless overridden.
        default_rules = list(units.get("*", ()))
        scenario_scoped: dict[str, Any] = {
            str(key): rules for key, rules in units.items() if key != "*"
        }
    else:
        default_rules = []
        scenario_scoped = {}

    results: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for version in versions:
        for scenario in scenarios:
            for rollout in rollouts:
                rel = pattern.format(version=version, scenario=scenario, rollout=rollout)
                path = transcripts_dir / rel
                if not path.is_file():
                    missing.append(str(path))
                    continue
                text = path.read_text(encoding="utf-8")
                env: dict[str, Any] = {}
                rules = list(scenario_scoped.get(scenario, ())) + list(default_rules)
                entry: dict[str, Any] = {"transcript": rel}
                for rule in rules:
                    if isinstance(rule, Mapping):
                        field, value = _apply_rule(rule, text, env)
                        entry[field] = value
                key = f"{version}:{scenario}" if single_rollout else f"{version}:{scenario}:{rollout}"
                results[key] = entry

    return {"results": results, "meta": {"missing_transcripts": missing}}


def write_checks(manifest: RunManifest, payload: dict[str, Any]) -> Path:
    """Serialize a :func:`run_checks` payload to the manifest's ``deterministic_checks`` path."""
    out_path = manifest.resolve("deterministic_checks")
    out_path = out_path.with_suffix(".json")
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return out_path
