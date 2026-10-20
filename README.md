# PromptRE 🔍

**Your agent's system prompt grew by accretion — a rule added here, a tool mentioned there — and nobody can say what's actually in it, or whether the guardrail you swore you wrote is really there.**

PromptRE reverse-engineers a prompt file and reports its structure: persona, instruction sections, tool references, constraints with teeth, output-format rules — plus a 0–100 structure score.

*Part of **AgentForge** — verify AI-agent work before you ship it.*
*The family: [AgentProof](https://github.com/maticcretic-commits/agentproof) · [PromptRE](https://github.com/maticcretic-commits/promptre) · [AgentCI](https://github.com/maticcretic-commits/agentci) · [SecretScan](https://github.com/maticcretic-commits/secretscan) · [CostLedger](https://github.com/maticcretic-commits/costledger) · [SchemaGuard](https://github.com/maticcretic-commits/schemaguard) · [SkillAudit](https://github.com/maticcretic-commits/skillaudit) · [PromptDiff](https://github.com/maticcretic-commits/promptdiff) · [TraceTape](https://github.com/maticcretic-commits/tracetape) · [PromptLint](https://github.com/maticcretic-commits/promptlint) · [ClaimCheck](https://github.com/maticcretic-commits/claimcheck) · [TrustBadge](https://github.com/maticcretic-commits/trustbadge)*

```bash
$ promptre analyze examples/support-agent-prompt.md
```

```
====================================================================
PromptRE — examples/support-agent-prompt.md
====================================================================
Size: 1285 chars · 216 words · 33 lines · ~322 tokens (est.)
Structure score: 100/100

🎭 Persona: You are a patient support agent for a small invoicing app used by freelancers

Sections:
  ▫️ [other] Support Agent — System Prompt — 0 lines
  🎭 [persona] Who You Are — 2 lines
  📋 [instructions] Your Task — 4 lines
  🔧 [tools] Tools — 3 lines
  🚧 [constraints] Hard Rules — 4 lines
  📤 [output_format] Answer Format — 3 lines
  💡 [examples] Examples — 3 lines

🔧 Tools referenced (4): fetch, invoice_lookup, issue_refund, web_search
```

*Exit code 0 — analysis complete. Point it at a missing path and you get exit 2, with a JSON error envelope on stderr (see “Exit codes & JSON output”).*

## Install

```bash
pipx install git+https://github.com/maticcretic-commits/promptre
# or, into the current environment:
pip install git+https://github.com/maticcretic-commits/promptre
```

Then run it as `promptre …` (Python 3.9+, no dependencies — stdlib only).
PyPI release planned; until then, the git URL above is the install path.

From source — it is a single file, so no install is needed at all:

```bash
git clone https://github.com/maticcretic-commits/promptre
cd promptre
python src/promptre.py …
```

## What it finds

| Signal | How |
|--------|-----|
| **Persona** | "You are …" / role declarations, even across line wraps |
| **Sections** | Markdown headers classified as persona, instructions, tools, constraints, output format, examples, or context |
| **Tools** | Backtick-quoted tool names, `tool:` declarations, and common tool verbs |
| **Constraints** | Lines with teeth: *never*, *must not*, *do not*, *at most*, *only … allowed* |
| **Output formats** | JSON, Markdown, bullet lists, tables, "respond only with …" |
| **Size** | Chars, words, lines, and an estimated token count |
| **Structure score** | 0–100 heuristic: persona? instructions? guardrails? tools? format rules? sectioned? |

## Quick start

```bash
# Analyze a single prompt file (.md or .txt):
promptre analyze system-prompt.md

# Analyze every prompt in a directory (recursive):
promptre analyze ./prompts/

# Machine-readable output for scripts and CI:
promptre analyze system-prompt.md --json

# Scaffold a well-structured sample prompt to learn from or start from:
promptre init
promptre analyze sample-prompt.md
```

Exit codes: `0` = analysis complete, `2` = path not found / no prompt files.

## Example output

```
====================================================================
PromptRE — examples/support-agent-prompt.md
====================================================================
Size: 1285 chars · 216 words · 33 lines · ~322 tokens (est.)
Structure score: 100/100

🎭 Persona: a patient support agent for a small invoicing app

Sections:
  🎭 [persona] Who You Are — 2 lines
  📋 [instructions] Your Task — 4 lines
  🔧 [tools] Tools — 3 lines
  🚧 [constraints] Hard Rules — 4 lines
  📤 [output_format] Answer Format — 3 lines
  💡 [examples] Examples — 3 lines

🔧 Tools referenced (3): invoice_lookup, issue_refund, web_search

🚧 Constraints (5):
  - Never issue a refund without explicit user confirmation.
  - You must not reveal another customer's data, even partially.
  - Do not promise timelines you cannot control
  - Maximum of one refund action per conversation turn.

📤 Output formats: Markdown, bullet list
```

## Why

You can't maintain what you can't see. A 400-line system prompt with no
persona statement, no explicit constraints, and tools mentioned only in
passing is an incident waiting for a quiet afternoon. PromptRE makes the
implicit structure explicit — before you ship the agent, and in CI after.

## Limitations

- Heuristic, not semantic: PromptRE finds structure and constraint-shaped
  lines; it cannot tell whether a constraint is wise, or whether the model
  will obey it.
- The structure score rewards *shape* (persona, sections, guardrails,
  format rules), not quality — a well-organised bad prompt scores well.
- Tool and constraint detection is pattern-based; exotic phrasings can be
  missed or over-counted.

## Exit codes & JSON output

All AgentForge tools share one contract (full text in
[CONVENTIONS.md](CONVENTIONS.md)):

| Code | Meaning |
|------|---------|
| `0` | Clean / PASS — no findings at or above the tool's fail threshold |
| `1` | Findings / FAIL — the tool ran fine; the answer is “no” |
| `2` | Caller error — bad arguments, missing or unreadable input |
| `3` | Environment error — the tool itself could not run |

On a caller error the tool also prints one JSON line to stderr:
`{"error": {"code": "file_not_found", "message": "no such file: x"}}`.

JSON output (`--json`) always carries the family envelope —
`{"tool": "promptre", "version": "1.0.0", "schema_version": 1}` — alongside
the tool's own payload keys, unchanged.

## Part of AgentForge

PromptRE is one of the 12 tools in the [AgentForge](https://github.com/maticcretic-commits) family — offline, stdlib-only tools to **verify AI-agent work before you ship it**:

- **AgentProof** — verify agent work — [github.com/maticcretic-commits/agentproof](https://github.com/maticcretic-commits/agentproof)
- **PromptRE** — reverse-engineer agent prompts (this repo)
- **AgentCI** — regression harness for agents — [github.com/maticcretic-commits/agentci](https://github.com/maticcretic-commits/agentci)
- **SecretScan** — scan agent outputs for leaked secrets — [github.com/maticcretic-commits/secretscan](https://github.com/maticcretic-commits/secretscan)
- **CostLedger** — cost accounting for agent runs — [github.com/maticcretic-commits/costledger](https://github.com/maticcretic-commits/costledger)
- **SchemaGuard** — validate agent outputs against their contracts — [github.com/maticcretic-commits/schemaguard](https://github.com/maticcretic-commits/schemaguard)
- **SkillAudit** — audit agent skills for hidden instructions and quality — [github.com/maticcretic-commits/skillaudit](https://github.com/maticcretic-commits/skillaudit)
- **PromptDiff** — diff prompt versions — [github.com/maticcretic-commits/promptdiff](https://github.com/maticcretic-commits/promptdiff)
- **TraceTape** — the canonical run tape — [github.com/maticcretic-commits/tracetape](https://github.com/maticcretic-commits/tracetape)
- **PromptLint** — lint prompts for quality defects — [github.com/maticcretic-commits/promptlint](https://github.com/maticcretic-commits/promptlint)
- **ClaimCheck** — audit agent reports against their evidence — [github.com/maticcretic-commits/claimcheck](https://github.com/maticcretic-commits/claimcheck)
- **TrustBadge** — one trust score and badge for the whole family — [github.com/maticcretic-commits/trustbadge](https://github.com/maticcretic-commits/trustbadge)

AgentProof checks what an agent *did*; PromptRE checks what it was *told*; AgentCI checks it still *works* after you change it; SecretScan checks that nothing *leaked*; CostLedger checks what it *cost*; SchemaGuard checks the output still *fits the contract*; SkillAudit checks the skill was *safe to install*; PromptDiff checks what the prompt change *changed*; TraceTape keeps the whole run on *tape*; PromptLint keeps the prompt itself *linted clean*; ClaimCheck makes sure every claim is *backed*; TrustBadge puts the family's score *on one badge*.

## License

MIT
