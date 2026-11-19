"""The rules that are never broken, written once (docs/decisions/0014): each is its decision record's Rule line, the
record marked "- **Never broken:** 7th in AGENTS.md's list", and kit/tools/build_docs.py writes AGENTS.md's list from
those lines in the order the marks give, and shows each whole in the decisions table; the same test and pre-commit hook
that keep the other generated files current keep the list so. Offline: a made-up clone, then the real records and
AGENTS.md."""
import hashlib
import re

import pytest
import yaml

from camkit import ROOT

import build_docs

AGENTS_HEAD = "# Briefing\n\n## Rules that are never broken\n\nWritten by hand.\n\n"
AGENTS_TAIL = "\nThe kit enforces most of them itself.\n"


def record(n: int, rule: str, mark: str = "", status: str = "accepted") -> str:
    return (f"# {n}. Record {n}\n\n- **Date:** 2026-11-0{n % 9 + 1}\n- **Status:** {status}\n"
            + (f"- **Never broken:** {mark}\n" if mark else "") + f"- **Rule:** {rule}\n\n## Context\n")


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A clone: three decision records, two of them rules that are never broken, the decisions index, and AGENTS.md
    with its rules' markers around a stale list."""
    d = tmp_path / "docs" / "decisions"
    d.mkdir(parents=True)
    (d / "0001-one.md").write_text(record(1, "Decisions are records."), encoding="utf-8")
    (d / "0002-two.md").write_text(record(2, "Never the second thing.", "2nd in AGENTS.md's list"), encoding="utf-8")
    (d / "0003-three.md").write_text(record(3, "Never the first thing.", "1st in AGENTS.md's list"), encoding="utf-8")
    (d / "index.md").write_text(f"# Decisions\n\n{build_docs.DECISIONS_START}\n{build_docs.DECISIONS_END}\n",
                                encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text(
        f"{AGENTS_HEAD}{build_docs.RULES_START}\n- a rule written by hand\n{build_docs.RULES_END}\n{AGENTS_TAIL}",
        encoding="utf-8")
    monkeypatch.setattr(build_docs, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(build_docs, "ROOT", tmp_path)
    return d


def test_the_marks_give_the_rules_and_their_order(tree):
    assert [(place, n, name) for place, n, name, _ in build_docs.never_broken_rules()] == [
        (1, 3, "0003-three.md"), (2, 2, "0002-two.md")]


@pytest.mark.parametrize("mark", ["yes", "first in AGENTS.md's list", "3th in AGENTS.md's list", "0th in AGENTS.md's list",
                                  "2nd in the playbook's list", ""])
def test_a_mark_that_gives_no_place_stops_the_build(tree, mark):
    """The mark says the rule's place, as an ordinal; anything else (a yes, a word, a wrong ending, no place) stops the
    build, saying how to write it, rather than leaving the rule out of AGENTS.md's list unseen."""
    (tree / "0001-one.md").write_text(record(1, "Decisions are records.").replace(
        "- **Rule:**", f"- **Never broken:** {mark}\n- **Rule:**".replace(" \n", "\n")), encoding="utf-8")
    with pytest.raises(SystemExit, match=r"0001-one\.md: its Never broken line .*'- \*\*Never broken:\*\* 7th in AGENTS\.md's list'"):
        build_docs.never_broken_rules()
    with pytest.raises(SystemExit, match=r"0001-one\.md: its Never broken line"):
        build_docs.decisions_index()


def test_two_rules_in_one_place_or_a_place_left_empty_stop_the_build(tree):
    (tree / "0001-one.md").write_text(record(1, "Decisions are records.", "2nd in AGENTS.md's list"), encoding="utf-8")
    with pytest.raises(SystemExit, match=r"0001-one\.md and docs/decisions/0002-two\.md both take the 2nd place"):
        build_docs.never_broken_rules()
    (tree / "0001-one.md").write_text(record(1, "Decisions are records.", "4th in AGENTS.md's list"), encoding="utf-8")
    with pytest.raises(SystemExit, match=r"no 3rd rule: the marked records take places 1, 2 and 4; give them 1 to 3"):
        build_docs.never_broken_rules()


def test_a_withdrawn_record_is_no_rule(tree):
    (tree / "0002-two.md").write_text(record(2, "Never the second thing.", "2nd in AGENTS.md's list",
                                             status="withdrawn 2026-11-19; replaced by 3"), encoding="utf-8")
    with pytest.raises(SystemExit, match=r"0002-two\.md is withdrawn and marked Never broken"):
        build_docs.never_broken_rules()


def test_a_rule_never_broken_is_shown_whole_in_the_table(tree):
    """A rule that is never broken is the whole rule an agent obeys, longer than the table's sentence: the table shows
    it whole. Past NEVER_BROKEN_CHARS the build stops, and its message never reads as advice to move a condition out of
    the rule: it says to raise the bound instead, and that only mechanism may stand in the record's Decision. A record
    not so marked keeps RULE_CHARS. The real rules keep room below the bound."""
    whole = "Never the first thing, " + "nor anything like it, " * 12 + "whoever asks."
    assert build_docs.RULE_CHARS < len(whole) < build_docs.NEVER_BROKEN_CHARS
    (tree / "0003-three.md").write_text(record(3, whole, "1st in AGENTS.md's list"), encoding="utf-8")
    assert f"| 3 | [Record 3](0003-three.md) | {whole} |" in build_docs.decisions_index()
    (tree / "0001-one.md").write_text(record(1, whole), encoding="utf-8")
    with pytest.raises(SystemExit, match=rf"0001-one\.md: its Rule line is {len(whole)} characters.*at most {build_docs.RULE_CHARS}"):
        build_docs.decisions_index()
    endless = "Never " + "this, " * 300 + "nor that."
    assert len(endless) > build_docs.NEVER_BROKEN_CHARS
    (tree / "0001-one.md").write_text(record(1, "Decisions are records."), encoding="utf-8")
    (tree / "0003-three.md").write_text(record(3, endless, "1st in AGENTS.md's list"), encoding="utf-8")
    with pytest.raises(SystemExit) as stop:
        build_docs.decisions_index()
    said = str(stop.value)
    assert said.startswith(f"docs/decisions/0003-three.md: its Rule line, a rule that is never broken, is {len(endless)} "
                           f"characters, past the {build_docs.NEVER_BROKEN_CHARS}")
    assert "keep every condition and exception in the Rule line" in said and "raise that bound" in said
    assert "move how the kit holds to it" not in said


def test_the_real_rules_keep_room_below_the_bound():
    """No rule sits so near NEVER_BROKEN_CHARS that a narrowing clause would not fit (a fifth of it to spare)."""
    for _, n, _, rule in build_docs.never_broken_rules():
        assert len(rule) <= build_docs.NEVER_BROKEN_CHARS * 0.8, (n, len(rule))


# ---------------------------------------------------------------- AGENTS.md's list, generated

def test_agents_md_lists_the_marked_rules_in_their_order(tree):
    """Each rule a bullet, its Rule line as written and a link to its record, in the marks' order; a record not marked
    is no rule there; what stands outside the markers stays as written."""
    text = build_docs.agents_rules()
    assert text == (f"{AGENTS_HEAD}{build_docs.RULES_START}\n\n"
                    "- Never the first thing ([decision 3](docs/decisions/0003-three.md)).\n"
                    "- Never the second thing ([decision 2](docs/decisions/0002-two.md)).\n"
                    f"\n{build_docs.RULES_END}\n{AGENTS_TAIL}")


def test_a_rule_s_links_lead_from_the_repository_s_root(tree):
    """A record links from docs/decisions/; AGENTS.md sits at the repository's root, so each link's target is made one
    from there: another record, a page of the docs with its heading, a heading of the record itself. Another site's
    stays as it is. The decisions table shows the links' text alone, as for every record."""
    (tree / "0003-three.md").write_text(record(
        3, "Never the first thing, as [decision 1](0001-one.md) says, [section 10](../GUIDE.md#10-stopping) shows, "
           "[the record's own words](#decision) and [the vendor](https://example.com/a#b) too.",
        "1st in AGENTS.md's list"), encoding="utf-8")
    assert ("- Never the first thing, as [decision 1](docs/decisions/0001-one.md) says, "
            "[section 10](docs/GUIDE.md#10-stopping) shows, [the record's own words](docs/decisions/0003-three.md#decision) "
            "and [the vendor](https://example.com/a#b) too ([decision 3](docs/decisions/0003-three.md)).\n"
            ) in build_docs.agents_rules()
    assert ("| Never the first thing, as decision 1 says, section 10 shows, the record's own words and the vendor too. |"
            ) in build_docs.decisions_index()


def test_agents_md_without_its_markers_stops_the_build(tree):
    (tree.parents[1] / "AGENTS.md").write_text(AGENTS_HEAD + "- a rule written by hand\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="AGENTS.md has lost its markers"):
        build_docs.agents_rules()


def test_agents_md_is_kept_current_as_the_other_generated_files_are():
    """AGENTS.md is one of the files build_docs.py writes, so --check (CI), the drift test
    (test_build_docs.test_every_generated_file_is_current) and the pre-commit hook hold it to the records; the hook runs
    when a record or AGENTS.md itself changes (a list edited by hand is written over)."""
    assert build_docs.GENERATED[ROOT / "AGENTS.md"] is build_docs.agents_rules
    cfg = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    hook = next(h for repo in cfg["repos"] for h in repo["hooks"] if h["id"] == "build-generated")
    for path in ("AGENTS.md", "docs/decisions/0004-never-delete-or-format-the-cards.md", "kit/tools/build_docs.py"):
        assert re.search(hook["files"], path), path
    assert not re.search(hook["files"], "docs/AGENTS.md") and "AGENTS.md's rules" in hook["name"]


def test_the_real_list_is_current_and_its_links_lead_somewhere():
    """AGENTS.md's list is what the records give now, one bullet a rule, and every link in it reaches a file of the
    repository, its #heading a heading there (GitHub's way of naming them)."""
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert text == build_docs.agents_rules()
    listed = text[text.index(build_docs.RULES_START):text.index(build_docs.RULES_END)]
    assert len(re.findall(r"^- ", listed, re.M)) == len(ORDER)
    for target in re.findall(r"\]\(([^)]+)\)", listed):
        if "://" in target:
            continue
        path, _, anchor = target.partition("#")
        assert (ROOT / path).is_file(), target
        if anchor:
            heads = {re.sub(r"[^\w\- ]", "", h).strip().lower().replace(" ", "-")
                     for h in re.findall(r"^#+ (.+)$", (ROOT / path).read_text(encoding="utf-8"), re.M)}
            assert anchor in heads, target


# ---------------------------------------------------------------- the real records

ORDER =[2, 3, 4, 5, 6, 7, 21, 8, 24, 9, 10, 15, 16]          # AGENTS.md's order on 2026-11-19, kept by the marks

# what each rule must go on saying, whatever its wording: the prohibitions and the narrow exceptions as AGENTS.md held
# them before its list was generated. A safety rule changes only with the maintainer's decision (docs/decisions/0001):
# a Rule line that drops one of these fails here, and so is never weakened by an edit nobody meant as a change
MUST_SAY = {
    2: ["Nothing that makes sound, light or motion is changed remotely", "by the owner's hand",
        "The one picture for the Playback rows is taken only on the owner's word", "own terminal", "never an agent"],
    3: ["Screen Reader", "only with headphones in and its volume at the lowest first", "the owner's word each time"],
    4: ["Never format or delete a card.", "a dated owner decision in its reviewed scope", "names the row by its path",
        "`kit/drive.py --owner --confirm` run's armed last press opens or confirms it", "typed the row's name",
        "no flag answers it", "only `\"unattended\": true` in the decision waives it",
        "the owner types the answer themselves", "an agent never answers it for them"],
    5: ["Never Initialize, Reset Network Set. or SSID/PW Reset", "only the narrowest, only if the owner allows it",
        "with their file put back after", "a dated owner decision in its reviewed scope", "`\"link_loss\": true`",
        "`kit/drive.py --owner --confirm` run's last press", "typed the row's name", "never an agent for them",
        "`RESTORE_BY_HAND.json`", "no link opens until `kit/tools/upload_check.py` has put its start file back",
        "Initialize never."],
    6: ["No hand-made settings files", "never by editing a file", "uploads only files that camera wrote",
        "checked by its bytes", "never writes a file through it"],
    7: ["C4 only as guarded Help", "on a menu or option screen whose footer draws the help button", "never in Playback",
        "with a picture displayed", "nor on the shooting screen",
        "where the body lists its operating mode, C4 also needs the camera to give one that is not Playback",
        "or whether the body lists it, cannot be read", "C1-C3 and C5-C7 never."],
    21: ["No key but MENU on the shooting screen", "unless the run names the key for that press",
         "`kit/drive.py --on-shooting KEY`, on the owner's word",
         "only on a body where it is known what that key does there", "on another body, its owner's word first",
         "none but MENU with no screen read", "never C4 or Delete"],
    8: ["USB settings, language, NTSC/PAL, area and date", "network identity", "changed by the owner's hand",
        "no `--allow` opens one of them, whatever the owner said", "only where the owner's dated decision names it",
        "never in Language, NTSC/PAL or Area/Date/Time",
        "In a row whose choice drops a link, starts a connection or a pairing, or changes what no file puts back, a "
        "`--network` run (a look lap) never chooses", "a dated owner decision in the camera's reviewed scope",
        "only with `\"link_loss\": true`, as the armed last press of a `kit/drive.py --owner --confirm` run",
        "typed the row's name, never an agent for them",
        "unless a run names that row with `--allow`, the owner's word"],
    24: ["may open any row to look at", "up, down and MENU alone", "local readers only", "keeping no screen's text",
         "never what never opens", "only by the owner's own run", "first-open procedure",
         "chooses an option only where a dated owner decision names it",
         "The body's serial number screen opens only on a look lap or the owner route, which save its frames black."],
    9: ["Credentials are never typed, read, OCR'd, screenshotted or stored", "opened only on a look lap",
        "frames saved black", "a dated owner decision in its reviewed scope", "for `kit/drive.py --owner`",
        "nothing ever typed", "`\"values\": \"logged\"`", "never in the console, the proof viewer or a packed copy"],
    10: ["The camera is free for tests", "physical actions", "visual checks", "menu routes are tried first"],
    15: ["Every run starts from a known file and ends restoring it", "STOP file", "a run is never killed",
         "nor the camera disconnected", "with a dialog open"],
    16: ["The owner's values never reach a definition, the data files or the docs", "names and value meanings only",
         "stay in the mapper's private evidence", "is not planned"],
}


# Each rule that is never broken pinned whole: its first words, for a failure one can read, and the first 16 hex
# digits of the SHA-256 of its Rule line as AGENTS.md lists it (links and all, its spaces made single, so a record
# wrapped anew keeps its pin). A safety rule changes only with the maintainer's decision (docs/decisions/0001): any change
# to one, a clause added as much as a clause dropped, fails here until the same commit pins the new line, which the
# failure prints; MUST_SAY above says what a deliberate change must still say
PINNED = {
    2: ("Nothing that makes sound, light or motion is", "12e8c79136d08940"),
    3: ("The camera's Screen Reader is changed remotely only", "98160dfbfddf43f1"),
    4: ("Never format or delete a card. The one", "a573426477dbc3df"),
    5: ("Never Initialize, Reset Network Set. or SSID/PW Reset;", "25aaf3b24d351a15"),
    6: ("No hand-made settings files: the kit, and whoever", "1b296585c7a77428"),
    7: ("C4 only as guarded Help, on a menu", "9959409b5807e95c"),
    21: ("No key but MENU on the shooting screen,", "e43aeb27a3b9e609"),
    8: ("USB settings, language, NTSC/PAL, area and date, and", "491de25eee2aa3b7"),
    24: ("A look lap, a run of `kit/drive.py` or", "b97c4f8318819e6f"),
    9: ("Credentials are never typed, read, OCR'd, screenshotted or", "c646458046751346"),
    10: ("The camera is free for tests, which run", "20b96a6faaa7d4ff"),
    15: ("Every run starts from a known file and", "64431308393734b7"),
    16: ("The owner's values never reach a definition, the", "0c97dcd1abcccd27"),
}


def pin(rule: str) -> tuple:
    return " ".join(rule.split()[:8]), hashlib.sha256(rule.encode("utf-8")).hexdigest()[:16]


def test_every_rule_never_broken_is_pinned():
    """A record newly marked Never broken is pinned too, and a pin outlives no rule."""
    assert sorted(PINNED) == sorted(ORDER)


@pytest.mark.parametrize("n", ORDER)
def test_no_rule_changes_unless_the_test_changes_with_it(n):
    """Each Rule line is the one pinned, word for word: an edit nobody meant as a change, a narrowing clause moved out
    or a widening one let in, fails here, naming the record and printing the pin a deliberate change gives."""
    name, rule = next((name, rule) for _, m, name, rule in build_docs.never_broken_rules() if m == n)
    assert pin(rule) == PINNED[n], (
        f"docs/decisions/{name}: its Rule line, a rule that is never broken, is not the line pinned here (it began "
        f"{PINNED[n][0]!r}). A safety rule changes only with the maintainer's decision (docs/decisions/0001), and AGENTS.md "
        f"lists it as written: put the record back, or, if the change is the maintainer's, pin it in the same commit as "
        f"PINNED[{n}] = {pin(rule)!r}")


def test_the_records_marked_never_broken_are_agents_md_s_rules_in_its_order():
    rules = build_docs.never_broken_rules()
    assert [n for _, n, _, _ in rules] == ORDER
    assert [place for place, _, _, _ in rules] == list(range(1, len(ORDER) + 1))
    for _, n, _, rule in rules:
        assert rule.endswith(".") and len(rule) <= build_docs.NEVER_BROKEN_CHARS, n


@pytest.mark.parametrize("n", ORDER)
def test_no_rule_says_less_than_it_did(n):
    rule = next(rule for _, m, _, rule in build_docs.never_broken_rules() if m == n)
    for said in MUST_SAY[n]:
        assert said in rule, f"decision {n}'s Rule line no longer says {said!r}"
