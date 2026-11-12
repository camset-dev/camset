"""Table cells (kit/proving/tables.py), off the camera: the way to a cell is found by the table the reader sees now,
its lit cell's box against the column the walk saw, not by the walked x alone. 2026-11-08: Image Quality Settings
drew one column (SLOT 1 only, the camera recording to one slot) centred at x 464, where the walk had seen two (SLOT 1
at 376, SLOT 2 at 548); to_cell pressed Left towards 376, nothing moved, and the cell failed. A fake camera stands in
for the screen, in both layouts."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from proving import tables  # noqa: E402
from proving.base import Failed  # noqa: E402

ROWS = [120, 176, 228, 284]                     # File Format, RAW File Type, JPEG Quality, JPEG Image Size
TWO = [(292, 460), (464, 632)]                  # SLOT 1, SLOT 2: the layout the walk saw
ONE = [(296, 632)]                              # SLOT 1 alone, 336 px wide
WALKED = [376, 548]                             # the walked columns' x (table_jobs' "columns")


class Table:
    """The Image Quality Settings table as the reader sees it: the lit cell's box and centre. Arrows move the cursor
    within the grid and stop at its edges (a Left in the one-column layout moves nothing)."""
    def __init__(self, columns, col=0, row=0):
        self.columns, self.col, self.row, self.presses = columns, col, row, []
        self.frame = SimpleNamespace(path=Path("00376_right.png"))

    def read(self):
        x0, x1 = self.columns[self.col]
        return SimpleNamespace(kind="table", focus="cell", boxes=[(x0, x1)], marker=((x0 + x1) // 2, ROWS[self.row]))

    def press(self, key):
        self.presses.append(key)
        if key in ("left", "right"):
            self.col = max(0, min(len(self.columns) - 1, self.col + (1 if key == "right" else -1)))
        else:
            self.row = max(0, min(len(ROWS) - 1, self.row + (1 if key == "down" else -1)))


def test_the_one_column_cell_is_the_first_walked_column():
    cam = Table(ONE)
    tables.to_cell(cam, [379, 120], columns=WALKED)              # SLOT 1 as the job carries it: no press at all
    assert cam.presses == [] and tables.on_table_cell(cam.read(), [379, 120], WALKED)
    cam = Table(ONE, row=3)                                      # from JPEG Image Size up to File Format
    tables.to_cell(cam, [376, 120], columns=WALKED)
    assert cam.presses == ["up"] * 3


def test_a_later_slots_cell_is_never_taken_for_the_first():
    """SLOT 2's walked x lies inside the one wide column too, which is SLOT 1's: it fails in plain words, nothing
    pressed, rather than proving SLOT 1's records under SLOT 2's name."""
    cam = Table(ONE)
    assert tables.table_column(cam.read(), [548, 120], WALKED) == "gone"
    assert not tables.on_table_cell(cam.read(), [548, 120], WALKED)
    with pytest.raises(Failed, match=r"shows fewer columns than the walk saw \(2\), and the cell at \[548, 120\] is in "
                                     r"one it no longer shows"):
        tables.to_cell(cam, [548, 120], columns=WALKED)
    assert cam.presses == []


def test_the_two_column_layout_is_walked_as_before():
    cam = Table(TWO, col=1, row=2)                               # SLOT 2, JPEG Quality, to SLOT 1, File Format
    tables.to_cell(cam, [376, 120], columns=WALKED)
    assert cam.presses == ["up", "up", "left"]
    assert tables.table_column(cam.read(), [376, 120], WALKED) == "here"
    cam = Table(TWO, col=0, row=0)
    tables.to_cell(cam, [548, 176], columns=WALKED)
    assert cam.presses == ["down", "right"] and tables.on_table_cell(cam.read(), [548, 176], WALKED)
    assert tables.table_column(Table(TWO, col=0).read(), [548, 120], WALKED) == "right"
    assert tables.table_column(Table(TWO, col=1).read(), [376, 120], WALKED) == "left"


def test_a_press_that_moves_nothing_still_fails():
    """The camera skips cells that are off; a press that moves nothing towards a cell outside the lit box fails."""
    cam = Table(TWO, col=1)
    cam.press = lambda key: cam.presses.append(key)              # the cursor stays put
    with pytest.raises(Failed, match="left towards the cell at \\[376, 120\\] did not move the cursor"):
        tables.to_cell(cam, [376, 120], columns=WALKED)


def test_jobs_carry_the_walked_columns(tmp_path, monkeypatch):
    import json
    cells = [{"pos": [x, y], "row_label": label, "col_label": slot, "opens": "list", "wrapped": True,
              "options": [{"label": "RAW"}, {"label": "JPEG"}]}
             for y, label in ((120, "File Format"), (228, "JPEG Quality")) for x, slot in ((376, "SLOT 1"), (548, "SLOT 2"))]
    f = tmp_path / "tables.json"
    f.write_text(json.dumps({"Image Quality Settings": {"path": ["Image Quality Settings"], "screen": "table",
                                                        "cells": cells}}), encoding="utf-8")
    monkeypatch.setattr(tables.base, "TABLES", f)
    jobs = tables.table_jobs()
    assert len(jobs) == 4 and all(j["columns"] == WALKED for j in jobs)
    job = next(j for j in jobs if j["option"] == "File Format / SLOT 1")
    assert tables.on_cell(Table(ONE), job) and not tables.on_cell(Table(ONE), dict(job, cell=[548, 120]))


# ---------------------------------------------------------------- old proof lines named by the walked table

def legacy(option, x, y, path=("Image Quality Settings",), nth=0):
    """A table proof line as written before 2026-11-11: its cell named by its own reading of the row."""
    return {"path": list(path), "kind": "table", "screen": "table", "nth": nth, "option": option, "cell": [x, y],
            "index": 0, "label": "A"}


def walk(*cells, path=("Image Quality Settings",), screen="table"):
    """A tables.json of one screen: cells (x, y, row_label, col_label)."""
    return {path[0]: {"path": list(path), "screen": screen, "nth": 0, "cells": [
        {"pos": [x, y], "row_label": row, "col_label": col} for x, y, row, col in cells]}}


def test_an_old_lines_glued_value_is_left_out_by_the_walked_cell_at_its_place():
    """A cell further right read the value of the cell before it glued on ("File Format <value>", decision 16); the
    walk read it otherwise (the camera held another value by then): the walked cell at the line's place names it, the
    value never in it, whatever the line itself read. Made-up values."""
    from camkit import match
    tbl = walk((376, 120, "dFile Format", "SLOT 1"), (548, 120, "•File Format HEIF", "SLOT 2"))
    named, unwalked = match.cell_options([legacy("•File Format RAW & HEIF / SLOT 2", 548, 120)], tbl)
    assert [r["option"] for r in named] == ["File Format / SLOT 2"] and unwalked == {}


def test_two_cells_whose_readings_clean_to_one_name_stay_two():
    """Two rows whose readings clean to one name (a mark before one, "--" after it): the walk
    names a repeated name by its place, and each line goes to the cell at its own place, never one row for both."""
    from camkit import match
    tbl = walk((448, 196, "Rear Dial", ""), (448, 248, "•Rear Dial --", ""), path=("My Dial Settings",))
    lines = [legacy("Rear Dial", 448, 196, path=("My Dial Settings",)),
             legacy("•Rear Dial --", 448, 248, path=("My Dial Settings",))]
    named, unwalked = match.cell_options(lines, tbl)
    assert [r["option"] for r in named] == ["Rear Dial @448,196", "Rear Dial @448,248"] and unwalked == {}
    assert len({r["option"] for r in named}) == 2


def test_a_line_no_walked_cell_matches_keeps_its_own_name_and_is_reported():
    """A line whose place no walked cell holds (the table walked again, laid out otherwise) is not given a neighbour's
    name: it keeps its own reading, cleaned, with its place, and the reason comes back for the report."""
    from camkit import match
    tbl = walk((376, 120, "dFile Format", "SLOT 1"))
    lines = [legacy("•File Format RAW / SLOT 2", 548, 120), legacy("dFile Format / SLOT 1", 376, 120),
             legacy("dFile Format / SLOT 1", 376, 120, nth=1)]
    named, unwalked = match.cell_options(lines, tbl)
    assert [r["option"] for r in named] == ["File Format RAW / SLOT 2 @548,120", "File Format / SLOT 1",
                                            "File Format / SLOT 1 @376,120"], "another nth is another table"
    assert set(unwalked) == {"File Format RAW / SLOT 2 @548,120", "File Format / SLOT 1 @376,120"}
    assert all("548,120" in why or "376,120" in why for why in unwalked.values())


def test_with_no_table_file_every_old_cell_keeps_a_name_of_its_own(tmp_path):
    """No tables.json: no line is merged with another by its reading; each keeps its own, with its place, and the
    report says so (pass2_report: UNWALKED_CELLS, the row's "cell_name", report.md). A Fn Menu tile and a line named
    by its place stay as they were."""
    import json
    import pass2_report as R
    from camkit import match
    lines = [legacy("dFile Format / SLOT 1", 376, 120), legacy("•File Format RAW / SLOT 2", 548, 120),
             {**legacy("Still Upper / 1", 0, 0, path=("Fn Menu Settings",)), "screen": "fnmenu"},
             legacy("JPEG Quality @376,228", 376, 228)]
    named, unwalked = match.cell_options(lines, None)
    assert [r["option"] for r in named] == ["File Format / SLOT 1 @376,120", "File Format RAW / SLOT 2 @548,120",
                                            "Still Upper / 1", "JPEG Quality @376,228"]
    assert set(unwalked) == {"File Format / SLOT 1 @376,120", "File Format RAW / SLOT 2 @548,120"}
    assert all("no table file" in why for why in unwalked.values())
    run = tmp_path / "kit2_pass2"
    run.mkdir()
    (run / "proofs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
    R.report_proofs(run)
    assert set(R.UNWALKED_CELLS) == {"Image Quality Settings / File Format / SLOT 1 @376,120",
                                     "Image Quality Settings / File Format RAW / SLOT 2 @548,120"}
    R.write_md(run, [], [], [], [], "report", R.UNWALKED_CELLS)
    assert "Table cells named by their own reading (2)" in (run / "report.md").read_text(encoding="utf-8")


def test_jobs_and_old_lines_name_a_cell_alike(tmp_path, monkeypatch):
    """table_jobs and the report's naming of old lines are one rule (match.walked_cell_names)."""
    import json
    from camkit import match
    tbl = walk((376, 120, "dFile Format", "SLOT 1"), (548, 120, "•File Format JPEG", "SLOT 2"), (376, 176, "", ""))
    for c in tbl["Image Quality Settings"]["cells"]:
        c.update(opens="list", wrapped=True, options=[{"label": "RAW"}, {"label": "JPEG"}])
    f = tmp_path / "tables.json"
    f.write_text(json.dumps(tbl), encoding="utf-8")
    monkeypatch.setattr(tables.base, "TABLES", f)
    jobs = tables.table_jobs()
    lines = [legacy("whatever was read", *j["cell"]) for j in jobs]
    assert [r["option"] for r in match.cell_options(lines, tbl)[0]] == [j["option"] for j in jobs] == \
        ["File Format / SLOT 1", "File Format / SLOT 2", "@376,176"]


def test_the_runs_own_one_column_frame():
    """Opt-in: the a1 II's frame of the one-column table (skipped without it, as in CI)."""
    from camkit import paths, screen
    from camkit.frames import load
    frame = paths.a1ii_root() / "kit2_review_list" / "shots" / "00376_right.png"
    if not frame.exists():
        pytest.skip("the a1 II's kit2_review_list frames are not in this clone")
    s = screen.read(load(frame))
    assert s.kind == "table" and s.focus == "cell"
    assert tables.on_table_cell(s, [379, 120], WALKED) and tables.table_column(s, [548, 120], WALKED) == "gone"


# ---------------------------------------------------------------- a cell's list walked by the labels on screen

class OptionList:
    """A table cell's option list as the reader sees it (kind "list", the lit row, no scrollbar) and OCR reads it, the
    saved option's radio read as an "O" in front. Down and Up move the cursor and come round at the ends, as the
    camera's lists do (the walk saw each one wrap)."""
    def __init__(self, options, row=0, saved=0):
        self.options, self.row, self.saved, self.presses = list(options), row, saved, []
        self.frame = SimpleNamespace(path=Path("01226_enter.png"))

    def read(self):
        top = tables.screen.LIST_ROW_TOP + self.row * tables.screen.LIST_ROW_PITCH
        return SimpleNamespace(kind="list", row=self.row, count=len(self.options), scroll=None, current=self.saved,
                               bar=(top, top + 47))

    def lines(self):
        from camkit import ocr
        return [ocr.Line(text=("O" if i == self.saved else "") + t, conf=0.99, x=125,
                         y=tables.screen.LIST_ROW_TOP + i * tables.screen.LIST_ROW_PITCH + 10, w=300, h=28)
                for i, t in enumerate(self.options)]

    def press(self, key):
        self.presses.append(key)
        self.row = (self.row + (1 if key == "down" else -1)) % len(self.options)


@pytest.fixture
def screen_text(monkeypatch, tmp_path):
    """OCR reads whatever the fake list draws now; its frame is a file the reader can be handed."""
    def use(cam):
        cam.frame = SimpleNamespace(path=tmp_path / "01226_enter.png")
        cam.frame.path.write_bytes(b"a frame")
        monkeypatch.setattr(tables.ocr, "read", lambda ps, eng=None: {p: cam.lines() for p in ps})
        monkeypatch.setattr(tables, "vlm_option", lambda cam: "")
        return cam
    return use


WALKED_LABELS = ["RAW", "O JPEG"]                   # what the two-slot walk saw in File Format's list (October)
JOB = {"labels": WALKED_LABELS, "frames": None}


def test_a_three_option_list_is_walked_by_its_labels(screen_text):
    """2026-11-08: recording to one slot, File Format's list shows RAW, RAW & JPEG and JPEG. One Down by the walk's count
    landed on RAW & JPEG; by the labels on screen JPEG is two rows down."""
    cam = screen_text(OptionList(["RAW", "RAW & JPEG", "JPEG"], row=0))
    assert tables.list_options(cam) == ["ORAW", "RAW & JPEG", "JPEG"]
    seen = tables.to_option(cam, WALKED_LABELS, 0, 1, "list", JOB, "File Format / SLOT 1")
    assert cam.presses == ["down", "down"] and cam.row == 2 and seen == ["ORAW", "RAW & JPEG", "JPEG"]
    cam = screen_text(OptionList(["RAW", "RAW & JPEG", "JPEG"], row=2, saved=2))
    tables.to_option(cam, WALKED_LABELS, 1, 0, "list", JOB, "File Format / SLOT 1")
    assert cam.presses == ["up", "up"] and cam.row == 0


def test_a_list_as_long_as_the_walk_saw_is_stepped_by_position(screen_text, monkeypatch):
    """As many options as the walk saw: stepped by position (move_to), as before, whatever OCR makes of their icons;
    the options seen are still recorded, and no reader is asked."""
    monkeypatch.setattr(tables, "ask_second", lambda *a, **k: pytest.fail("the reader was asked"))
    cam = screen_text(OptionList(["RAW", "JPEG"], row=1, saved=1))
    assert tables.to_option(cam, WALKED_LABELS, 1, 0, "list", JOB, "File Format / SLOT 1") == ["RAW", "OJPEG"]
    assert cam.presses == ["down"] and cam.row == 0                  # one step round, as move_to takes it
    # RAW File Type's five options, two of them read by OCR as no label matches ("Lossless Comp (M) KAW")
    walked = ["RAW Uncompressed", "RAW Lossless Comp (L)", "Lossless Comp (M) KAW", "RAW Lossless Comp (S)", "RAW Compressed"]
    shown = ["RAW Uncompressed", "RAWL Lossless Comp", "Lossless Comp (M) -M", "RAW Lossless Comp (S)", "RAW Compressed"]
    cam = screen_text(OptionList(shown, row=0))
    monkeypatch.setattr(tables, "option_index", lambda cam, labels, kind, job: cam.row)     # the walk's row, by place
    tables.to_option(cam, walked, 0, 2, "list", JOB, "RAW File Type / SLOT 2")
    assert cam.presses == ["down", "down"] and cam.row == 2


class Reader:
    """The vision reader as ask_second asks it (the menu question): its rows, or nothing; counts the questions."""
    def __init__(self, rows):
        self.rows, self.asked = rows, []

    def __call__(self, image, prompt, timeout):
        self.asked.append(prompt)
        if isinstance(self.rows, Exception):
            raise self.rows
        return {"rows": [{"label": r} for r in self.rows]}


def test_a_label_ocr_cannot_find_is_asked_of_the_reader_before_the_row_fails(screen_text, monkeypatch):
    """Another count than the walk's, and OCR finds no row for the wanted label ("JPFG"): the vision reader is asked
    once, and its reading of the rows decides."""
    reader = Reader(["RAW", "RAW & JPEG", "JPEG"])
    monkeypatch.setattr(tables, "ask_second", reader)
    cam = screen_text(OptionList(["RAW", "RAW & JPEG", "JPFG"], row=0))
    monkeypatch.setattr(tables, "option_index", lambda cam, labels, kind, job: 1 if cam.row == 2 else None)
    assert tables.to_option(cam, WALKED_LABELS, 0, 1, "list", JOB, "File Format / SLOT 1") == ["ORAW", "RAW & JPEG", "JPFG"]
    assert cam.presses == ["down", "down"] and reader.asked == [tables.PROMPTS["menu"]]


@pytest.mark.parametrize("answer,said", [(["RAW", "RAW & JPEG"], "RAW · RAW & JPEG"), (OSError("the reader is off"), "nothing")])
def test_a_label_the_list_does_not_show_is_never_chosen(screen_text, monkeypatch, answer, said):
    reader = Reader(answer)
    monkeypatch.setattr(tables, "ask_second", reader)
    cam = screen_text(OptionList(["RAW", "RAW & JPEG"], row=0))
    with pytest.raises(Failed, match=r"File Format / SLOT 1: 'O JPEG' is not one of the options the list shows \(OCR read "
                                     rf"ORAW · RAW & JPEG; the vision reader {said}\), so it is not chosen"):
        tables.to_option(cam, WALKED_LABELS + ["RAW+J"], 0, 1, "list", JOB, "File Format / SLOT 1")
    assert cam.presses == [] and len(reader.asked) == 1


def test_the_proof_records_the_options_the_list_showed(screen_text, monkeypatch):
    """prove_table_row with every other camera step faked: the 'RAW' and 'JPEG' proofs carry the list's own options."""
    import io
    import json

    class Camera(OptionList):
        def __init__(self):
            super().__init__(["RAW", "RAW & JPEG", "JPEG"], row=2, saved=2)
            self.at = "row"

        def read(self):
            return super().read() if self.at == "list" else SimpleNamespace(kind={"row": "menu"}.get(self.at, "table"))

        def press(self, key):
            if self.at == "list" and key in ("down", "up"):
                return super().press(key)
            self.presses.append(key)
            if key == "right" and self.at == "row":
                self.at = "table"
            elif key == "enter" and self.at == "table":
                self.at, self.row = "list", self.saved          # the list opens on the saved option
            elif key == "enter" and self.at == "list":
                self.at, self.saved = "cell", self.row
            elif key == "enter" and self.at == "ok":
                self.at = "row"
    cam = screen_text(Camera())
    for fn in ("to_row", "to_cell", "after_download"):
        monkeypatch.setattr(tables, fn, lambda *a, **k: None)
    monkeypatch.setattr(tables, "place", lambda cam: cam.at)
    monkeypatch.setattr(tables, "same_place", lambda a, b: a == b)
    monkeypatch.setattr(tables, "first_time_notice", lambda cam: False)
    monkeypatch.setattr(tables, "on_cell", lambda cam, job: cam.at == "cell")
    monkeypatch.setattr(tables, "cell_value", lambda cam: cam.options[cam.saved])
    monkeypatch.setattr(tables, "to_ok", lambda cam: setattr(cam, "at", "ok"))
    monkeypatch.setattr(tables, "camset", SimpleNamespace(read=lambda p: p, diff=lambda a, b: []))
    job = {"path": ["Image Quality Settings"], "kind": "table", "screen": "table", "option": "File Format / SLOT 1",
           "cell": [376, 120], "columns": WALKED, "opens": "list", "labels": WALKED_LABELS, "frames": None}
    out = io.StringIO()
    link = SimpleNamespace(download=lambda tag: Path(f"{tag}.DAT"))
    tables.prove_table_row(cam, link, None, job, Path("base.DAT"), out)
    proofs = [json.loads(line) for line in out.getvalue().splitlines()]
    assert [p["label"] for p in proofs] == ["RAW", "O JPEG"]
    assert all(p["options_seen"][1] == "RAW & JPEG" and len(p["options_seen"]) == 3 for p in proofs)
    assert cam.presses.count("down") == 2 and cam.presses.count("up") == 2      # RAW from JPEG, then JPEG back


def test_the_october_walks_cells_reach_every_option_on_their_own_frames(monkeypatch):
    """Opt-in: every list cell of the a1 II's October table walk (kit2_tables), each proof in the prover's own order,
    on the walk's own frames (a fake camera shows the frame of the option the cursor is on; Down and Up go to the next
    and the previous). All 22 reach their option: the lists as long as the walk saw are stepped by position, whatever
    OCR makes of their icons (skipped without the frames, as in CI)."""
    from camkit import paths, screen
    from camkit.frames import load
    import proving.options as options
    walked = paths.a1ii_root() / "kit2_tables" / "tables.json"
    if not walked.exists():
        pytest.skip("the a1 II's kit2_tables walk is not in this clone")
    monkeypatch.setattr(tables.base, "TABLES", walked)
    monkeypatch.setattr(options, "vlm_option", lambda cam: "")
    monkeypatch.setattr(tables, "ask_second", lambda *a, **k: pytest.fail("the reader was asked"))

    class WalkCam:
        def __init__(self, frames, at):
            self.frames, self.at = frames, at
            self.show()

        def show(self):
            self.frame = load(walked.parent / "shots" / self.frames[self.at])
            self.screen = screen.read(self.frame)

        def read(self):
            return self.screen

        def press(self, key):
            self.at = (self.at + (1 if key == "down" else -1)) % len(self.frames)
            self.show()
    jobs = [j for j in tables.table_jobs() if j["opens"] == "list" and j.get("screen", "table") == "table"]
    reached = []
    for j in jobs:
        cur = 0
        for k in tables.table_order(j, 0):
            tables.to_option(WalkCam(j["frames"], cur), j["labels"], cur, k, "list", j, j["option"])
            reached.append((j["option"], k))
            cur = k
    assert len(jobs) == 8 and len(reached) == 22
