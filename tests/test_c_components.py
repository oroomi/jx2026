"""Direction C components (jx37): the macros render on their own, and a company with
no signals never produces an empty box or a placeholder that could read as data."""
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "radar" / "templates"
CSS = ROOT / "radar" / "static" / "c_components.css"
TOKENS = ROOT / "radar" / "static" / "tokens.css"

# Viva Jets Oy 2962040-6, exactly as the committed snapshot holds it.
VIVA = [
    {"date": "2018-12-28", "label": "Register entry"},
    {"date": "2019-01-01", "label": "Business Finland funding"},
    {"date": "2021-01-01", "label": "Business Finland funding"},
    {"date": "2024-01-01", "label": "Business Finland funding"},
]


def _mod(name="_c_components.html"):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    return env.get_template(name).module


# --- a company with no signals -------------------------------------------------

def test_sparkline_with_no_signals_is_hatched_not_empty():
    out = str(_mod().sparkline([]))
    assert "c-spark-none" in out and "no public evidence yet" in out
    assert "<polyline" not in out and "<circle" not in out


def test_lifeline_with_no_signals_says_so():
    out = str(_mod().lifeline([], "x"))
    assert "no public evidence yet" in out and "c-none" in out
    assert "<svg" not in out


def test_every_macro_renders_on_a_company_with_nothing():
    m = _mod()
    for out in (str(m.sparkline(None)), str(m.lifeline(None, "u")), str(m.verdict_pill(None)),
                str(m.key_stats([])), str(m.key_stats(None))):
        assert out.strip(), "a macro returned nothing at all"
    assert "no verdict yet" in str(m.verdict_pill(None))


def test_key_stats_hatches_a_missing_value_instead_of_a_dash():
    out = str(_mod().key_stats([
        {"label": "Founded", "value": None, "source_url": None},
        {"label": "Business ID", "value": "2962040-6", "source_url": "https://example.org/x"},
    ]))
    assert out.count("no public evidence yet") == 1
    assert ">-<" not in out and ">&mdash;<" not in out
    assert '<a href="https://example.org/x">2962040-6</a>' in out


# --- real data -----------------------------------------------------------------

def test_sparkline_marks_the_newest_signal():
    out = str(_mod().sparkline(VIVA))
    assert "<polyline" in out and out.count("<circle") == 1, "one dot, on the newest"
    pts = re.search(r'points="([^"]+)"', out).group(1).split()
    assert len(pts) == len(VIVA)
    xs = [float(p.split(",")[0]) for p in pts]
    assert xs == sorted(xs), "time runs left to right"
    ys = [float(p.split(",")[1]) for p in pts]
    assert ys == sorted(ys, reverse=True), "the running count only rises"


def test_sparkline_is_the_requested_size_and_needs_no_script():
    out = str(_mod().sparkline(VIVA, width=80, height=24))
    assert 'width="80"' in out and 'height="24"' in out
    assert "<script" not in out and "onclick" not in out


def test_lifeline_ranges_are_css_only_and_max_is_the_default():
    out = str(_mod().lifeline(VIVA, "viva", today="2026-10-17"))
    assert "<script" not in out
    assert out.count('type="radio"') == 3
    checked = re.search(r'id="ll-viva-(\w+)"\s+checked', out)
    assert checked and checked.group(1) == "max", "MAX is the no-JS default"
    # 1Y holds no Viva Jets record; the pane says so rather than drawing an empty axis
    pane = out.split('c-ll-1y')[1].split('c-ll-3y')[0]
    assert "no public record in this range" in pane


def test_lifeline_radio_group_is_unique_per_instance():
    a = str(_mod().lifeline(VIVA, "one"))
    b = str(_mod().lifeline(VIVA, "two"))
    assert 'name="ll-one"' in a and 'name="ll-two"' in b
    assert 'name="ll-one"' not in b


def test_verdict_pill_tones():
    m = _mod()
    for verdict, tone in (("Watchlist", "grey"), ("Accelerator", "teal"),
                          ("Partner introduction", "teal"), ("Invest", "green"),
                          ("Due diligence", "green"), ("Reject / low fit", "red")):
        out = str(m.verdict_pill(verdict))
        assert f"c-pill-{tone}" in out, (verdict, out)
        assert verdict in out, "the word carries the meaning, never the colour alone"
    assert "c-pill-grey" in str(m.verdict_pill("Something new")), "unknown verdicts read neutral"


# --- the stylesheet ------------------------------------------------------------

def test_css_only_adds_namespaced_rules():
    css = CSS.read_text()
    selectors = re.findall(r"(?m)^([.#][^{\n]+)\{", css)
    for sel in selectors:
        assert ".c-" in sel, f"{sel} is not namespaced to this task"
    assert 'env(safe-area-inset-bottom' in css, "the tab bar clears the home indicator"
    assert "var(--c-tap)" in css, "tap targets go through one variable"


def test_every_variable_comes_from_tokens_css_or_is_a_c_addition():
    """The design session owns tokens.css. Anything this task needs beyond it must be --c-."""
    tokens = set(re.findall(r"(--[a-z0-9-]+)\s*:", TOKENS.read_text()))
    assert "--accent" in tokens and "--ok" in tokens, "tokens.css did not parse"
    used = set(re.findall(r"var\((--[a-z0-9-]+)", CSS.read_text()))
    unknown = {v for v in used if v not in tokens and not v.startswith("--c-")}
    assert not unknown, f"not in tokens.css and not prefixed --c-: {sorted(unknown)}"


def test_the_c_additions_are_declared_and_minimal():
    css = CSS.read_text()
    declared = set(re.findall(r"(--c-[a-z0-9-]+)\s*:", css))
    used = {v for v in re.findall(r"var\((--c-[a-z0-9-]+)", css)}
    assert used <= declared, f"used but never declared: {sorted(used - declared)}"
    # tokens.css has ok, warn, info and none but no red, so the pill supplies exactly that
    assert "--c-reject" in declared
    assert declared == {"--c-reject", "--c-reject-soft", "--c-tap", "--c-tabbar-h"}, sorted(declared)


def test_verdict_pill_green_and_grey_come_from_tokens_not_from_new_colours():
    css = CSS.read_text()
    assert "var(--ok)" in css, "green is the tokens status colour"
    assert "var(--none)" in css, "grey is the tokens status colour"
    assert "var(--accent)" in css, "teal is the one accent"


def test_tabbar_has_five_destinations_and_no_emoji():
    out = str(_mod("_tabbar.html").tabbar("lists"))
    for label in ("Radar", "Search", "Lists", "Backtest", "Data"):
        assert f">{label}</span>" in out
    assert out.count("<li>") == 5
    assert 'aria-current="page"' in out and out.count('aria-current="page"') == 1
    assert not re.search(r"[\U0001F300-\U0001FAFF☀-➿]", out), "no emoji, per CLAUDE.md"
