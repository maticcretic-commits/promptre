"""Tests for PromptRE analysis core and CLI."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from promptre import (analyze_text, analyze_path, estimate_tokens,
                      extract_persona, extract_tools, split_sections,
                      classify_section)

SRC = Path(__file__).parent.parent / "src" / "promptre.py"

SAMPLE = """# System Prompt — Research Bot

## Role
You are a meticulous research assistant for an operations team.

## Instructions
1. Restate the question.
2. Search with `web_search` before answering.
3. Write the briefing with the `write` tool.

## Constraints
- Never invent a figure or date.
- You must cite a source for every claim.
- Do not exceed 600 words.

## Output Format
Respond in Markdown with a bullet list and a sources table.
"""


# --- section detection ------------------------------------------------------

def test_sections_split_on_headers():
    parts = split_sections(SAMPLE)
    titles = [t for t, _ in parts]
    assert "Role" in titles
    assert "Instructions" in titles
    assert "Constraints" in titles


def test_headerless_text_is_one_preamble():
    parts = split_sections("Just a blob of prompt text.\nNo headers here.")
    assert len(parts) == 1
    assert parts[0][0] == "Preamble"


def test_section_classification():
    a = analyze_text(SAMPLE)
    kinds = {s.kind for s in a.sections}
    assert "persona" in kinds
    assert "instructions" in kinds
    assert "constraints" in kinds
    assert "output_format" in kinds


def test_classify_by_title_keywords():
    assert classify_section("Available Tools", "call them") == "tools"
    assert classify_section("Safety Rules", "be careful") == "constraints"


# --- persona extraction -----------------------------------------------------

def test_persona_extracted_from_role_section():
    assert "meticulous research assistant" in extract_persona(SAMPLE)


def test_persona_extracted_inline():
    text = "You are a friendly coding tutor.\nAlways be patient."
    assert extract_persona(text) == "a friendly coding tutor"


def test_persona_absent_returns_empty():
    assert extract_persona("Do the thing. Then do the other thing.") == ""


# --- tools / constraints / formats ------------------------------------------

def test_tools_extracted():
    tools = extract_tools(SAMPLE)
    assert "web_search" in tools
    assert "write" in tools


def test_constraints_extracted():
    a = analyze_text(SAMPLE)
    joined = " ".join(a.constraints)
    assert "Never invent" in joined
    assert "must cite" in joined


def test_output_formats_detected():
    a = analyze_text(SAMPLE)
    assert "Markdown" in a.output_formats
    assert "bullet list" in a.output_formats


# --- token estimate ----------------------------------------------------------

def test_token_estimate_empty():
    assert estimate_tokens("") == 0
    assert estimate_tokens("   ") == 0


def test_token_estimate_reasonable():
    text = "word " * 100  # 100 words, 500 chars
    est = estimate_tokens(text)
    assert 100 <= est <= 200


# --- empty / edge handling ----------------------------------------------------

def test_empty_text_analysis():
    a = analyze_text("")
    assert a.empty is True
    assert a.structure_score == 0
    assert a.est_tokens == 0
    assert a.sections == []


def test_whitespace_only_is_empty():
    a = analyze_text("  \n\n  ")
    assert a.empty is True


def test_score_full_for_well_structured_prompt():
    a = analyze_text(SAMPLE)
    assert a.structure_score >= 80, a.score_notes


def test_score_low_for_flat_prompt():
    a = analyze_text("Answer questions helpfully and be nice about it.")
    assert a.structure_score < 50


# --- file / directory analysis ------------------------------------------------

def _write(d, name, content):
    p = Path(d) / name
    p.write_text(content)
    return p


def test_analyze_txt_file():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, "agent.txt", SAMPLE)
        results = analyze_path(p)
        assert len(results) == 1
        assert results[0].persona != ""


def test_analyze_directory_recurses():
    with tempfile.TemporaryDirectory() as d:
        _write(d, "a.md", SAMPLE)
        sub = Path(d) / "sub"
        sub.mkdir()
        _write(sub, "b.txt", "You are a poet. Write verses.")
        _write(d, "skip.py", "print('not a prompt')")
        results = analyze_path(Path(d))
        assert len(results) == 2
        assert all(not r.empty for r in results)


def test_analyze_empty_file_on_disk():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, "empty.md", "")
        results = analyze_path(p)
        assert results[0].empty is True


# --- CLI ----------------------------------------------------------------------

def run_cli(*argv):
    return subprocess.run([sys.executable, str(SRC), *argv],
                          capture_output=True, text=True)


def test_cli_json_output_valid():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, "agent.md", SAMPLE)
        r = run_cli("analyze", str(p), "--json")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)  # must be valid JSON
        assert isinstance(data, dict)
        assert isinstance(data["results"], list) and len(data["results"]) == 1
        item = data["results"][0]
        assert item["persona"]
        assert item["est_tokens"] > 0
        assert "web_search" in item["tools"]
        assert item["structure_score"] >= 80
        kinds = {s["kind"] for s in item["sections"]}
        assert "constraints" in kinds


def test_cli_text_output():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, "agent.md", SAMPLE)
        r = run_cli("analyze", str(p))
        assert r.returncode == 0, r.stderr
        assert "Structure score" in r.stdout
        assert "Persona" in r.stdout


def test_cli_missing_path_errors():
    r = run_cli("analyze", "/nonexistent/nope.md")
    assert r.returncode == 2


def test_cli_init_scaffolds_analyzable_sample():
    with tempfile.TemporaryDirectory() as d:
        r = run_cli("init", "--dir", d)
        assert r.returncode == 0, r.stderr
        sample = Path(d) / "sample-prompt.md"
        assert sample.exists()
        r2 = run_cli("analyze", str(sample), "--json")
        data = json.loads(r2.stdout)
        assert data["results"][0]["structure_score"] >= 80


# --- envelope / version / error envelope -------------------------------------

def test_cli_json_envelope_keys():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, "agent.md", SAMPLE)
        r = run_cli("analyze", str(p), "--json")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert isinstance(data, dict)
        assert data["tool"] == "promptre"
        assert data["version"] == "1.0.0"
        assert "schema_version" in data
        assert "results" in data
        assert isinstance(data["results"], list)


def test_cli_version():
    r = run_cli("--version")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "promptre 1.0.0"


def test_cli_missing_path_error_envelope():
    r = run_cli("analyze", "/nonexistent/nope.md")
    assert r.returncode == 2
    # stderr must contain a JSON error envelope line with code file_not_found
    found = None
    for line in r.stderr.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "error" in obj:
                found = obj
                break
    assert found is not None, r.stderr
    assert found["error"]["code"] == "file_not_found"
    assert "no such file or directory" in found["error"]["message"]


def test_cli_json_schema_version_is_int_1():
    with tempfile.TemporaryDirectory() as d:
        p = _write(d, "agent.md", SAMPLE)
        r = run_cli("analyze", str(p), "--json")
        assert r.returncode == 0, r.stderr
        data = json.loads(r.stdout)
        assert data["schema_version"] == 1
        assert type(data["schema_version"]) is int
