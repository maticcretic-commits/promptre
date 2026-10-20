# PromptRE 🔍

**Your agent has a prompt. What's actually inside it?**

Agent prompts, skill files, and system prompts grow by accretion — a rule
added here, a tool mentioned there, a constraint someone swore they wrote
but didn't. PromptRE reverse-engineers them: point it at a prompt file and
it reports the structure — persona, instruction sections, tool references,
constraints, output-format rules — plus a structure score.

```bash
python src/promptre.py analyze my-agent-prompt.md
python src/promptre.py analyze prompts/ --json   # whole folders, for CI
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

## Part of AgentForge

PromptRE is the second tool in the [AgentForge](https://github.com/maticcretic-commits)
trust layer for AI agents:

- **AgentProof** — verify agent work — [github.com/maticcretic-commits/agentproof](https://github.com/maticcretic-commits/agentproof)
- **PromptRE** — reverse-engineer agent prompts (this repo)
- **AgentCI** — regression harness for agents — [github.com/maticcretic-commits/agentci](https://github.com/maticcretic-commits/agentci)
- **SecretScan** — scan agent outputs for leaked secrets — [github.com/maticcretic-commits/secretscan](https://github.com/maticcretic-commits/secretscan)
- **CostLedger** — cost accounting for agent runs — [github.com/maticcretic-commits/costledger](https://github.com/maticcretic-commits/costledger)

AgentProof checks what an agent *did*; PromptRE checks what it was *told*; AgentCI checks it still *works* after you change it; SecretScan checks that nothing *leaked*; CostLedger checks what it *cost*.

## License

MIT
