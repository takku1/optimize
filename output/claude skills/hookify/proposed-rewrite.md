---
name: writing-hookify-rules
description: Use this skill when the user asks to create, write, configure, add, refine, test, or disable a Hookify rule, or needs help with Hookify rule syntax, events, conditions, or patterns.
version: 0.2.0
---

# Writing Hookify Rules

Create and maintain Hookify rules: Markdown files with YAML frontmatter that
match hook events and display a message, optionally blocking the operation.

## Rule location and file shape

Store rules at the project root in:

```text
.claude/hookify.{descriptive-name}.local.md
```

Use kebab-case names that start with an action, such as
`hookify.warn-dangerous-rm.local.md` or `hookify.require-tests.local.md`.
Keep local rules out of version control when appropriate by adding
`.claude/*.local.md` to `.gitignore`.

Every rule has YAML frontmatter followed by the message shown when it matches:

```markdown
---
name: warn-dangerous-rm
enabled: true
event: bash
action: warn
pattern: rm\s+-rf
---

Dangerous recursive removal detected. Verify the target before continuing.
```

## Frontmatter

Required fields:

- `name`: unique, descriptive kebab-case identifier; prefer an action prefix
  such as `warn`, `prevent`, `block`, `require`, or `check`.
- `enabled`: `true` to activate or `false` to disable without deleting the rule.
- `event`: one of `bash`, `file`, `stop`, `prompt`, or `all`.

Optional fields:

- `action`: `warn` (default) displays the message and allows the operation;
  `block` prevents a matching pre-tool operation or stops a matching Stop event.
- `pattern`: a Python-compatible regular expression for one-field matching.
- `conditions`: a list of conditions for conjunctions across multiple fields.

Use either `pattern` or `conditions` for a rule. All conditions must match.

Event fields:

| Event | Typical fields | Use |
|---|---|---|
| `bash` | `command` | inspect shell commands |
| `file` | `file_path`, `new_text`, `old_text`, `content` | inspect edits and writes |
| `stop` | event-provided stop text | enforce completion checks |
| `prompt` | `user_prompt` | respond to request content |
| `all` | event-dependent | apply a deliberately broad rule |

Condition operators are `regex_match`, `contains`, `equals`, `not_contains`,
`starts_with`, and `ends_with`:

```yaml
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.env$
  - field: new_text
    operator: contains
    pattern: API_KEY
```

## Choosing events and patterns

1. Identify the unwanted or required behavior.
2. Select the narrowest event that observes it.
3. Select the field containing the relevant value.
4. Use `pattern` for one field or `conditions` for multiple fields.
5. Make the pattern specific enough to avoid common false positives.
6. Put a concise explanation and next action in the message.

Useful patterns:

```yaml
# bash: dangerous commands
pattern: (?:^|\s)(?:sudo\s+|rm\s+-rf|dd\s+if=|mkfs(?:\s|$))

# file: debug or risky code
pattern: (?:console\.log\(|debugger\b|eval\(|innerHTML\s*=)

# file: sensitive path plus secret content
conditions:
  - field: file_path
    operator: regex_match
    pattern: (?:^|[\\/])(?:\.env|credentials|.*\.pem)$
  - field: new_text
    operator: regex_match
    pattern: (?:API_KEY|SECRET|TOKEN)\s*=
```

Python regular-expression reminders:

- `\s` whitespace, `\d` digit, and `\w` word character;
- escape literal `.`, `(`, `)`, `[`, and `]`;
- `+` means one or more, `*` zero or more, `?` optional, and `|` alternation;
- in double-quoted YAML strings, escape backslashes again; unquoted patterns
  avoid that extra layer.

Avoid patterns that are merely `log`, `test`, or another common substring.
Prefer boundaries and the smallest expression that detects the behavior. A
pattern such as `rm -rf /tmp` is usually too specific; `rm\s+-rf` is more
useful when the target path is not the concern.

## Message design

The message is the intervention. It should say:

1. what matched;
2. why it matters; and
3. what to do next.

For example:

```markdown
⚠️ **Console logging detected.**

This may expose data or ship noisy production output. Use the project logger,
remove the debug statement, or confirm that this is an intentional test-only
log before continuing.
```

Use `action: block` only when the operation must not proceed automatically.
Use `warn` for advisory checks and include enough context for the user or agent
to make the decision.

## Common rule templates

### Bash safety

```markdown
---
name: block-dangerous-commands
enabled: true
event: bash
action: block
pattern: (?:^|\s)(?:rm\s+-rf|mkfs|dd\s+if=)
---

**Command blocked.** Review the target and use a narrowly scoped, recoverable
operation if deletion or disk modification is intended.
```

### File safety

```markdown
---
name: warn-console-log
enabled: true
event: file
action: warn
pattern: console\.log\(
---

**Debug logging detected.** Remove it or confirm that it is intentional and
safe for the target environment.
```

### Stop-time verification

```markdown
---
name: require-verification
enabled: true
event: stop
action: warn
pattern: .*
---

Before stopping, verify the relevant tests, build, documentation, and
uncommitted changes. Report anything that was not checked.
```

### Prompt-specific guidance

```markdown
---
name: check-production-deploy
enabled: true
event: prompt
action: warn
conditions:
  - field: user_prompt
    operator: contains
    pattern: deploy to production
---

Before deployment, confirm tests, review, rollback, monitoring, and the target
environment.
```

## Test and maintain rules

Test the exact expression against both matching and non-matching examples
before relying on it. With Python:

```bash
python3 -c "import re; print(bool(re.search(r'rm\\s+-rf', 'rm -rf build')))"
```

To refine a rule, edit its `.local.md` file; Hookify reads changes on the next
tool use. To disable it, set `enabled: false`. Delete the file only when the
rule is permanently unnecessary.

When creating a rule, report the path, event, action, and pattern or conditions
used. Do not create a broad `all`-event rule when a narrower event can express
the same protection.

For complete plugin-provided examples, see `${CLAUDE_PLUGIN_ROOT}/examples/`.
