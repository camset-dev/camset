"""kit/drive.py's lit-row match (glued_icon): the --path's own row read with its icon glued on, or before a label the
screen cut with an ellipsis ("SRegist. Face Priority On", "In Face Priority in Multi Mr On": mg_3's two drive steps of
2026-11-20 that drive.py refused, both rows seen opened on this body), is that row where the page model saw it drawn
with an icon, the words after it none or a value of it; a lit text that is another row whose label ends alike, or runs
on with words that are no value, is still refused, and so is a row the page model never saw with an icon. The page
model's readings are kit2_page_scan_movie_1118's for the two rows. Nothing talks to a camera."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
import drive  # noqa: E402
from camkit import first_open  # noqa: E402

ON_OFF = ["On", "Off"]
REGIST = {"label": "Regist. Face Priority",
          "readings": {"label": {"ocr": "in Regist. Face Priority", "ocr2": "Regist. Face Priority",
                                 "vllm": "Regist. Face Priority"}}}
MULTI = {"label": "Face Priority in Mul...",
         "readings": {"label": {"ocr": "& Face Priority in Mul...", "ocr2": "Face Priority in Mul",
                                "vllm": "Face Priority in Mul..."}}}
REGIST_VALUES = {"regist. face priority": ON_OFF}
MULTI_VALUES = {"face priority in mul": ON_OFF}
# the definition's name for the row the screen cuts, in runner.cut_names's shape
NAMES = {"face priority in mul": {"face priority in multi metering": ON_OFF}}


def judged(lit, row, values, others=(), names=NAMES):
    """lit_refused on the --path's own top-level page, the run having gone by the page scan to the page model's `row`."""
    label = row["label"]
    return drive.lit_refused(lit, [], [label], first_open.Seen({(label.lower(),)}), set(others), None, values,
                             (row, set()), names=names)


def test_a_label_read_with_its_icon_letter_glued_on_is_the_paths_row():
    assert judged("SRegist. Face Priority On", REGIST, REGIST_VALUES) == ("", ("Regist. Face Priority",))
    assert judged("SRegist. Face Priority", REGIST, REGIST_VALUES) == ("", ("Regist. Face Priority",))


def test_a_cut_label_read_on_past_its_ellipsis_behind_an_icon_word_is_the_paths_row():
    """The lit row shows more of the long label than the page scan read: "Multi Mr" for the definition's "Multi
    Metering", then the row's value."""
    want = ("", ("Face Priority in Mul...",))
    assert judged("In Face Priority in Multi Mr On", MULTI, MULTI_VALUES) == want
    assert judged("In Face Priority in Multi Metering Off", MULTI, MULTI_VALUES) == want
    assert judged("In Face Priority in Mul... On", MULTI, MULTI_VALUES) == want
    # the words read on past the cut must be the definition's name for that row: without it, nothing ties them
    why, row = judged("In Face Priority in Multi Mr On", MULTI, MULTI_VALUES, names={})
    assert why and row is None


def test_another_row_whose_label_ends_alike_is_still_refused():
    face = {"label": "Face Priority", "readings": {"label": {"ocr": "in Face Priority", "vllm": "Face Priority"}}}
    values = {"face priority": ON_OFF, **REGIST_VALUES}
    for lit in ("Regist. Face Priority On", "SRegist. Face Priority On"):
        why, row = judged(lit, face, values)
        assert why and row is None, f"{lit!r}: Regist. is no icon, the lit row is Regist. Face Priority"
    why, row = judged("Regist. Face Priority On", MULTI, {**MULTI_VALUES, **REGIST_VALUES})
    assert why and row is None
    # a short word the kit knows as the start of another row's label is no icon, however it is spaced
    for lit in ("AF Face Priority On", "AFFace Priority On"):
        why, row = judged(lit, face, values, others={"AF Face Priority"})
        assert why and row is None, lit


def test_words_after_the_label_that_are_no_value_or_word_of_it_are_still_refused():
    why, row = judged("SRegist. Face Priority Sideways", REGIST, REGIST_VALUES)
    assert why and row is None
    for lit in ("In Face Priority in Multi Mr Sideways", "In Face Priority in Multi Xr On",
                "In Face Priority in Mulch On", "In Face Priority in Multi Metering Frame On"):
        why, row = judged(lit, MULTI, MULTI_VALUES)
        assert why and row is None, lit


def test_a_row_the_page_model_never_saw_with_an_icon_takes_no_glued_letter():
    plain = {"label": "Regist. Face Priority", "readings": {"label": {"ocr": "Regist. Face Priority"}}}
    why, row = judged("SRegist. Face Priority On", plain, REGIST_VALUES)
    assert why and row is None


def test_the_icon_takes_at_most_four_characters():
    why, row = judged("Abcde Regist. Face Priority On", REGIST, REGIST_VALUES)
    assert why and row is None


def test_cut_names_are_the_definitions_names_of_the_rows_the_screen_cuts():
    from runner import cut_names
    doc = {"settings": [
        {"name": "Face Priority in Multi Metering", "row": ["Face Priority in Mul..."], "values": [[0, "On"], [1, "Off"]]},
        {"name": "Regist. Face Priority", "row": ["Regist. Face Priority"], "values": [[0, "On"], [1, "Off"]]}]}
    assert cut_names(doc) == {"face priority in mul": {"face priority in multi metering": {"On", "Off"}}}


def test_values_filed_under_labels_that_read_alike_are_kept_together():
    """runner.row_values files a value under every reading of a row ("Face Priority in Mul..." and OCR's "Face Priority
    in Mul"); compared plain the two are one label, and its values are both's, never the last one's alone (drive.py
    kept the last one's: kit2_page_scan_movie_1118 left this row "On" alone)."""
    assert drive.plain_values({"Face Priority in Mul...": {"On", "Off"}, "Face Priority in Mul": {"On"}}) == \
        {"face priority in mul": {"On", "Off"}}
