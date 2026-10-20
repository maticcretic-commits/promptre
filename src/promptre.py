#!/usr/bin/env python3
"""
PromptRE — "Your agent has a prompt. What's actually inside it?"

An open-source CLI that reverse-engineers AI agent prompts, skill files,
and system prompts. Point it at a .md or .txt file (or a directory of
them) and it reports the structure: persona, instruction sections, tool
references, constraints, output-format rules — plus a structure score.

Usage:
    promptre analyze <file-or-dir> [--json]
    promptre init [--force] [--dir PATH]    # scaffold a sample prompt
"""

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Section classification
#
# A prompt is split into sections by markdown headers (#, ##, ...) or,
# failing that, treated as one blob. Each section is then classified by
# keyword signals in its title and body.
# ---------------------------------------------------------------------------

SECTION_SIGNALS = {
    "persona": ["role", "persona", "identity", "who you are", "character",
                "you are", "about you"],
    "instructions": ["instruction", "task", "workflow", "process", "steps",
                     "how to", "procedure", "guidelines", "rules for"],
    "tools": ["tool", "function", "api", "command", "available actions",
              "capabilit"],
    "constraints": ["constraint", "limitation", "never", "must not", "do not",
                    "don't", "forbidden", "restriction", "safety",
                    "boundaries", "prohibited"],
    "output_format": ["output", "format", "response style", "answer format",
                      "formatting", "template", "structure of"],
    "examples": ["example", "sample", "few-shot", "few shot", "demonstration"],
    "context": ["context", "background", "knowledge", "reference",
                "information", "about the"],
}

# Bare tool-ish names frequently referenced in agent prompts. Matched as
# whole words so "reading" doesn't trip "read".
KNOWN_TOOLS = [
    "bash", "shell", "python", "node", "git", "curl", "grep", "sed", "awk",
    "read", "write", "edit", "search", "fetch", "browse", "browser",
    "calculator", "code_interpreter", "web_search", "image_gen",
    "file_search", "function_call", "tool_use", "api_call",
]

CONSTRAINT_PATTERNS = [
    re.compile(r"\bmust not\b", re.I),
    re.compile(r"\bmust never\b", re.I),
    re.compile(r"\bnever\b", re.I),
    re.compile(r"\bdo not\b", re.I),
    re.compile(r"\bdon't\b", re.I),
    re.compile(r"\bonly\b.{0,40}\b(allowed|permitted|use)\b", re.I),
    re.compile(r"\balways\b", re.I),
    re.compile(r"\bmust\b", re.I),
    re.compile(r"\brequired\b", re.I),
    re.compile(r"\bforbidden\b", re.I),
    re.compile(r"\bprohibited\b", re.I),
    re.compile(r"\bmaximum of\b", re.I),
    re.compile(r"\bat most\b", re.I),
]

OUTPUT_FORMAT_PATTERNS = [
    (re.compile(r"\bjson\b", re.I), "JSON"),
    (re.compile(r"\bmarkdown\b", re.I), "Markdown"),
    (re.compile(r"\bbullet", re.I), "bullet list"),
    (re.compile(r"\bnumbered list\b", re.I), "numbered list"),
    (re.compile(r"\btable\b", re.I), "table"),
    (re.compile(r"\byaml\b", re.I), "YAML"),
    (re.compile(r"\bxml\b", re.I), "XML"),
    (re.compile(r"\bcode block", re.I), "code block"),
    (re.compile(r"\bplain text\b", re.I), "plain text"),
    (re.compile(r"respond (only|with|in)", re.I), "constrained response"),
]

PERSONA_PATTERN = re.compile(
    r"(?:^|\s)(?:#+\s*)?(?:you are|your role is|act as|pretend to be|"
    r"role\s*[:\-])\s*([^\n.]{3,120})", re.I)


@dataclass
class Section:
    title: str
    kind: str  # persona|instructions|tools|constraints|output_format|examples|context|other
    lines: int
    chars: int


@dataclass
class PromptAnalysis:
    file: str
    empty: bool = False
    chars: int = 0
    words: int = 0
    lines: int = 0
    est_tokens: int = 0
    persona: str = ""
    sections: list = field(default_factory=list)
    section_kinds: list = field(default_factory=list)
    tools: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    output_formats: list = field(default_factory=list)
    headers: int = 0
    code_blocks: int = 0
    structure_score: int = 0  # 0-100
    score_notes: list = field(default_factory=list)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars/token for English-ish text, with a
    word-based floor so short dense prompts aren't undercounted."""
    if not text.strip():
        return 0
    by_chars = len(text) / 4.0
    by_words = len(text.split()) * 1.33
    return int(math.ceil(max(by_chars, by_words)))


def split_sections(text: str):
    """Split markdown text into (title, body) sections on # headers.
    Returns [("preamble", body)] for headerless text."""
    parts = re.split(r"(?m)^(#{1,6})\s+(.+)$", text)
    # re.split with groups: [pre, hashes, title, body, hashes, title, body...]
    sections = []
    pre = parts[0].strip()
    if pre:
        sections.append(("Preamble", pre))
    for i in range(1, len(parts), 3):
        title = parts[i + 1].strip()
        body = parts[i + 2].strip() if i + 2 < len(parts) else ""
        sections.append((title, body))
    if not sections:
        sections.append(("Preamble", text.strip()))
    return sections


def classify_section(title: str, body: str) -> str:
    title_l = title.lower()
    if not body.strip():
        # Header with no body: classify only when the title itself is a
        # short, keyword-led header ("Tools", "Output Format") — a long
        # document title ("System Prompt — Sample Agent") is just a title.
        words = re.findall(r"[a-z']+", title_l)
        if len(words) > 3:
            return "other"
        best, best_hits = "other", 0
        for kind, signals in SECTION_SIGNALS.items():
            hits = sum(1 for s in signals if s in title_l)
            if hits > best_hits:
                best, best_hits = kind, hits
        return best
    hay = (title + "\n" + body[:600]).lower()
    best, best_hits = "other", 0
    for kind, signals in SECTION_SIGNALS.items():
        hits = sum(1 for s in signals if s in hay)
        # Title matches weigh double — headers are deliberate structure.
        hits += sum(1 for s in signals if s in title_l)
        if hits > best_hits:
            best, best_hits = kind, hits
    return best


def extract_persona(text: str) -> str:
    # Flatten line wraps so a persona sentence split across lines
    # ("...app used by\nfreelancers.") still reads as one phrase.
    flat = re.sub(r"\s*\n\s*", " ", text)
    m = PERSONA_PATTERN.search(flat)
    if m:
        return m.group(1).strip().strip("*_`\"' ")
    return ""


def extract_tools(text: str) -> list:
    found = set()
    low = text.lower()
    # Backtick-quoted identifiers often name tools/commands: `web_search`
    for tok in re.findall(r"`([a-z][a-z0-9_.\-]{1,40})`", low):
        if "_" in tok or tok in KNOWN_TOOLS:
            found.add(tok)
    for tool in KNOWN_TOOLS:
        if re.search(rf"\b{re.escape(tool)}\b", low):
            found.add(tool)
    # tool_name: / "tools": style declarations
    for tok in re.findall(r"(?:tool|function)[\s\"']*[:=][\s\"']*([a-z][a-z0-9_.\-]{1,40})", low):
        found.add(tok)
    return sorted(found)


def extract_constraints(text: str) -> list:
    out, seen = [], set()
    for line in text.splitlines():
        s = line.strip().lstrip("-*# ").strip()
        if len(s) < 8 or len(s) > 220:
            continue
        if any(p.search(s) for p in CONSTRAINT_PATTERNS):
            key = s.lower()
            if key not in seen:
                seen.add(key)
                out.append(s)
    return out[:25]


def extract_output_formats(text: str) -> list:
    found = []
    for pat, label in OUTPUT_FORMAT_PATTERNS:
        if pat.search(text) and label not in found:
            found.append(label)
    return found


def score_structure(a: PromptAnalysis) -> tuple:
    """0-100 heuristic score: does this prompt have the bones of a
    maintainable agent prompt (persona, instructions, guardrails...)?"""
    if a.empty:
        return 0, ["empty file — nothing to score"]
    score, notes = 0, []
    kinds = set(a.section_kinds)
    if a.persona:
        score += 20
    else:
        notes.append("no explicit persona ('You are ...') found")
    if "instructions" in kinds or len(a.sections) >= 2:
        score += 20
    else:
        notes.append("no identifiable instruction section")
    if "constraints" in kinds or a.constraints:
        score += 20
    else:
        notes.append("no constraints/guardrails detected")
    if "tools" in kinds or a.tools:
        score += 15
    else:
        notes.append("no tool references detected")
    if a.output_formats or "output_format" in kinds:
        score += 15
    else:
        notes.append("no output-format rules detected")
    if a.headers >= 2:
        score += 10
    elif a.headers == 1:
        score += 5
        notes.append("only one header — consider sectioning long prompts")
    else:
        notes.append("no markdown headers — flat text is harder to maintain")
    return min(score, 100), notes


def analyze_text(text: str, name: str = "<text>") -> PromptAnalysis:
    a = PromptAnalysis(file=name)
    a.chars = len(text)
    a.words = len(text.split())
    a.lines = text.count("\n") + 1 if text else 0
    a.est_tokens = estimate_tokens(text)
    if not text.strip():
        a.empty = True
        a.structure_score, a.score_notes = score_structure(a)
        return a

    a.headers = len(re.findall(r"(?m)^#{1,6}\s+\S", text))
    a.code_blocks = text.count("```") // 2
    a.persona = extract_persona(text)

    for title, body in split_sections(text):
        kind = classify_section(title, body)
        a.sections.append(Section(
            title=title, kind=kind,
            lines=body.count("\n") + 1 if body else 0,
            chars=len(body)))
    a.section_kinds = sorted({s.kind for s in a.sections if s.kind != "other"})

    a.tools = extract_tools(text)
    a.constraints = extract_constraints(text)
    a.output_formats = extract_output_formats(text)
    a.structure_score, a.score_notes = score_structure(a)
    return a


def analyze_path(path: Path):
    """Analyze one file, or every .md/.txt under a directory.
    Returns a list of PromptAnalysis."""
    if path.is_dir():
        files = sorted(p for p in path.rglob("*")
                       if p.suffix.lower() in (".md", ".txt")
                       and p.is_file())
        return [analyze_text(p.read_text(encoding="utf-8", errors="replace"),
                             str(p)) for p in files]
    return [analyze_text(path.read_text(encoding="utf-8", errors="replace"),
                         str(path))]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

KIND_ICON = {
    "persona": "🎭", "instructions": "📋", "tools": "🔧",
    "constraints": "🚧", "output_format": "📤", "examples": "💡",
    "context": "📚", "other": "▫️",
}


def print_text_report(analyses):
    multi = len(analyses) > 1
    for a in analyses:
        print("=" * 68)
        print(f"PromptRE — {a.file}")
        print("=" * 68)
        if a.empty:
            print("File is empty — nothing to reverse-engineer.\n")
            continue
        print(f"Size: {a.chars} chars · {a.words} words · {a.lines} lines "
              f"· ~{a.est_tokens} tokens (est.)")
        print(f"Structure score: {a.structure_score}/100")
        for n in a.score_notes:
            print(f"  ⚠ {n}")
        print()
        print(f"🎭 Persona: {a.persona or '(none detected)'}")
        print()
        print("Sections:")
        if a.sections:
            for s in a.sections:
                print(f"  {KIND_ICON.get(s.kind, '▫️')} [{s.kind}] "
                      f"{s.title} — {s.lines} lines")
        else:
            print("  (none)")
        print()
        print(f"🔧 Tools referenced ({len(a.tools)}): "
              f"{', '.join(a.tools) if a.tools else '(none)'}")
        print()
        print(f"🚧 Constraints ({len(a.constraints)}):")
        for c in a.constraints[:10]:
            print(f"  - {c}")
        if not a.constraints:
            print("  (none detected)")
        print()
        print(f"📤 Output formats: "
              f"{', '.join(a.output_formats) if a.output_formats else '(none specified)'}")
        print(f"🧱 Code blocks: {a.code_blocks} · Headers: {a.headers}")
        print()
    if multi:
        ok = [a for a in analyses if not a.empty]
        if ok:
            avg = sum(a.structure_score for a in ok) / len(ok)
            print(f"Summary: {len(analyses)} files · "
                  f"avg structure score {avg:.0f}/100")


def _fail(code, message):
    print(f"error: {message}", file=sys.stderr)
    print(json.dumps({"error": {"code": code, "message": message}}),
          file=sys.stderr)
    sys.exit(2)


def cmd_analyze(args):
    path = Path(args.target)
    if not path.exists():
        _fail("file_not_found", f"no such file or directory: {path}")
    analyses = analyze_path(path)
    if not analyses:
        _fail("no_prompt_files", f"no .md or .txt files found under {path}")
    if args.json:
        print(json.dumps({
            "tool": "promptre",
            "version": VERSION,
            "schema_version": 1,
            "results": [asdict(a) for a in analyses],
        }, indent=2))
    else:
        print_text_report(analyses)


# ---------------------------------------------------------------------------
# init — scaffold a sample, well-structured agent prompt
# ---------------------------------------------------------------------------

SAMPLE_TEMPLATE = """# System Prompt — {name}

## Role
You are a research assistant for a small operations team. You turn rough
questions into short, sourced briefings the team can act on.

## Instructions
1. Restate the question in one line so misunderstandings surface early.
2. Gather facts with the `web_search` tool before answering.
3. Draft the briefing, then re-check every number against its source.

## Tools
- `web_search` — find current facts and sources.
- `read` / `write` — read input files and save the final briefing.

## Constraints
- Never invent a figure, date, or quote — if unverified, say so.
- You must cite a source for every factual claim.
- Do not exceed 600 words unless the user asks for more.

## Output Format
Respond in Markdown: a one-line summary, then a bullet list of findings,
then a "Sources" section. No code block around the whole answer.

## Examples
User: "What changed in the pricing page this week?"
Assistant: summary line, 3-5 findings with sources, Sources section.
"""


def cmd_init(args):
    base = Path(args.dir) if args.dir else Path.cwd()
    target = base / "sample-prompt.md"
    if target.exists() and not args.force:
        print(f"{target} exists — use --force to overwrite")
        return
    target.write_text(SAMPLE_TEMPLATE.format(name="Sample Agent"))
    print(f"created {target}")
    print("try it:  promptre analyze sample-prompt.md")


def main():
    ap = argparse.ArgumentParser(
        prog="promptre",
        description="Reverse-engineer agent prompts. "
                    "Your agent has a prompt — what's actually inside it?")
    ap.add_argument("--version", action="version",
                    version=f"promptre {VERSION}")
    ap.add_argument("--no-color", action="store_true",
                    help="disable ANSI color output (accepted harmlessly; "
                         "NO_COLOR env var is also honored)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    an = sub.add_parser("analyze", help="analyze a prompt file or directory")
    an.add_argument("target", help="path to a .md/.txt file or a directory")
    an.add_argument("--json", action="store_true",
                    help="machine-readable JSON output")
    an.set_defaults(fn=cmd_analyze)

    i = sub.add_parser("init", help="scaffold a sample structured prompt")
    i.add_argument("--force", action="store_true")
    i.add_argument("--dir", help="directory to write sample-prompt.md into")
    i.set_defaults(fn=cmd_init)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
