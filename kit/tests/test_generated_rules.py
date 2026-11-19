"""The rules that are never broken, written once (docs/decisions/0014): each is its decision record's Rule line, the
record marked "- **Never broken:** 7th in AGENTS.md's list", and kit/tools/build_docs.py shows that Rule line whole in
the decisions table. Offline: a made-up docs tree, then the real records."""
import pytest

import build_docs


def record(n: int, rule: str, mark: str = "", status: str = "accepted") -> str:
    return (f"# {n}. Record {n}\n\n- **Date:** 2026-11-0{n % 9 + 1}\n- **Status:** {status}\n"
            + (f"- **Never broken:** {mark}\n" if mark else "") + f"- **Rule:** {rule}\n\n## Context\n")


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A clone's docs: three decision records, two of them rules that are never broken, and the decisions index."""
    d = tmp_path / "docs" / "decisions"
    d.mkdir(parents=True)
    (d / "0001-one.md").write_text(record(1, "Decisions are records."), encoding="utf-8")
    (d / "0002-two.md").write_text(record(2, "Never the second thing.", "2nd in AGENTS.md's list"), encoding="utf-8")
    (d / "0003-three.md").write_text(record(3, "Never the first thing.", "1st in AGENTS.md's list"), encoding="utf-8")
    (d / "index.md").write_text(f"# Decisions\n\n{build_docs.DECISIONS_START}\n{build_docs.DECISIONS_END}\n",
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
    it whole. Its bound is NEVER_BROKEN_CHARS, past which the build stops (mechanism goes into the record's Decision);
    a record not so marked keeps RULE_CHARS."""
    whole = "Never the first thing, " + "nor anything like it, " * 12 + "whoever asks."
    assert build_docs.RULE_CHARS < len(whole) < build_docs.NEVER_BROKEN_CHARS
    (tree / "0003-three.md").write_text(record(3, whole, "1st in AGENTS.md's list"), encoding="utf-8")
    assert f"| 3 | [Record 3](0003-three.md) | {whole} |" in build_docs.decisions_index()
    (tree / "0001-one.md").write_text(record(1, whole), encoding="utf-8")
    with pytest.raises(SystemExit, match=rf"0001-one\.md: its Rule line is {len(whole)} characters.*at most {build_docs.RULE_CHARS}"):
        build_docs.decisions_index()
    endless = "Never " + "this, " * 200 + "nor that."
    assert len(endless) > build_docs.NEVER_BROKEN_CHARS
    (tree / "0001-one.md").write_text(record(1, "Decisions are records."), encoding="utf-8")
    (tree / "0003-three.md").write_text(record(3, endless, "1st in AGENTS.md's list"), encoding="utf-8")
    with pytest.raises(SystemExit, match=rf"0003-three\.md: its Rule line, a rule that is never broken, is {len(endless)} "
                                         rf"characters.*at most {build_docs.NEVER_BROKEN_CHARS}"):
        build_docs.decisions_index()


# ---------------------------------------------------------------- the real records

ORDER = [2, 3, 4, 5, 6, 7, 21, 8, 24, 9, 10, 15, 16]          # AGENTS.md's order on 2026-11-19, kept by the marks

# what each rule must go on saying, whatever its wording: the prohibitions and the narrow exceptions as AGENTS.md held
# them before its list was generated. A safety rule changes only with the maintainer's decision (docs/decisions/0001):
# a Rule line that drops one of these fails here, and so is never weakened by an edit nobody meant as a change
MUST_SAY = {
    2: ["Nothing that makes sound, light or motion is changed remotely", "by the owner's hand",
        "The one picture for the Playback rows is taken only on the owner's word", "own terminal", "never an agent"],
    3: ["Screen Reader", "only with headphones in and its volume at the lowest first", "the owner's word each time"],
    4: ["Never format or delete a card.", "dated owner decision in its reviewed scope", "names the row by its path",
        "`kit/drive.py --owner --confirm` run's armed last press opens or confirms it", "typed the row's name",
        "no flag answers it", "only `\"unattended\": true` in the decision waives it",
        "the owner types the answer themselves", "an agent never answers it for them"],
    5: ["Never Initialize, Reset Network Set. or SSID/PW Reset", "only the narrowest, only if the owner allows it",
        "with their file put back after", "`\"link_loss\": true`", "typed the row's name", "`RESTORE_BY_HAND.json`",
        "no link opens until `kit/tools/upload_check.py` has put its start file back", "Initialize never."],
    6: ["No hand-made settings files", "never by editing a file", "uploads only files that camera wrote",
        "checked by its bytes"],
    7: ["C4 only as guarded Help", "whose footer draws the help button", "never in Playback", "with a picture displayed",
        "nor on the shooting screen", "C1-C3 and C5-C7 never."],
    21: ["No key but MENU on the shooting screen", "unless the run names the key for that press",
         "none but MENU with no screen read", "never C4 or Delete"],
    8: ["USB settings, language, NTSC/PAL, area and date", "network identity", "changed by the owner's hand",
        "no `--allow` opens one of them, whatever the owner said", "only where the owner's dated decision names it",
        "never in Language, NTSC/PAL or Area/Date/Time"],
    24: ["may open any row to look at", "up, down and MENU alone", "local readers only", "keeping no screen's text",
         "never what never opens", "only by the owner's own run", "first-open procedure",
         "chooses an option only where a dated owner decision names it"],
    9: ["Credentials are never typed, read, OCR'd, screenshotted or stored", "opened only on a look lap",
        "frames saved black", "nothing ever typed", "`\"values\": \"logged\"`",
        "never in the console, the proof viewer or a packed copy"],
    10: ["The camera is free for tests", "physical actions", "visual checks", "menu routes are tried first"],
    15: ["Every run starts from a known file and ends restoring it", "STOP file", "never killed", "with a dialog open"],
    16: ["The owner's values never reach a definition, the data files or the docs", "names and value meanings only"],
}


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
