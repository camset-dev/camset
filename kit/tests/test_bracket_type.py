"""The Bracket Type carousel (the a1 II's Shooting > Drive Mode > Bracket Settings > Bracket Type, open only with the drive
mode dial on BRK): the pixel reader tells a carousel option's lit field from the option lit. The camera's frames these
read are found by their own path (camkit.paths.a1ii_root()), and those tests skip without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import paths, screen  # noqa: E402
from camkit.frames import Frame, load  # noqa: E402

A1 = paths.a1ii_root()
ORANGE = (200, 80, 20)
CONT = ((137, 345), (353, 563))                         # Cont. Bracket's two boxes, as drawn at y 351-406
FOCUS = ((137, 382), (393, 449), (449, 506), (506, 562))  # Focus Bracket's Step Width and its three digits


def need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} not present")
    return path


def carousel(lit=None, boxes=CONT, y=351, h=56) -> Frame:
    """A made-up carousel: the divider at x 112, the strip's option icon at the centre slot (orange while the option is
    lit, white once a field is), the option's boxes on one line, box `lit` filled orange and the others outlined in
    grey; digit boxes drawn side by side share a side."""
    a = np.zeros((480, 640, 3), np.uint8)
    a[5:420, 112] = 200
    a[195:230, 38:73] = ORANGE if lit is None else (230, 230, 230)
    for x0, x1 in boxes:
        for part in (a[y, x0:x1 + 1], a[y + h - 1, x0:x1 + 1], a[y:y + h, x0], a[y:y + h, x1]):
            part[...] = 85
    if lit is not None:
        x0, x1 = boxes[lit]
        a[y:y + h, x0:x1 + 1] = ORANGE
    return Frame(image=a, t=0.0)


def test_a_carousel_with_its_option_lit_reads_no_field():
    s = screen.read(carousel())
    assert s.kind == "dialog" and s.slots[screen.CENTRE] == "selected"
    assert s.field is None and s.boxes == [] and s.bar is None


@pytest.mark.parametrize("boxes, lit", [(CONT, 0), (CONT, 1), (FOCUS, 0), (FOCUS, 1), (FOCUS, 2), (FOCUS, 3)])
def test_a_lit_field_reads_its_index_among_the_boxes(boxes, lit):
    """Right from the option lights a box: the reader gives its index among the boxes on its line, and every box, the
    digit boxes that share their sides told apart."""
    s = screen.read(carousel(lit, boxes))
    assert s.kind == "dialog"
    assert s.field == lit and len(s.boxes) == len(boxes) and s.bar == (351, 406)
    assert s.boxes[lit] == boxes[lit]


def test_the_strip_and_the_title_are_never_a_field():
    """An orange block left of the divider (the strip's lit icon) or in the title band is no field."""
    f = carousel()
    f.image[60:110, 130:330] = ORANGE
    f.image[300:356, 20:100] = ORANGE
    s = screen.read(f)
    assert s.kind == "dialog" and s.field is None


BRK = [("kit2_fin_brtype_cont/shots/00005_right.png", None, 0),       # Cont. Bracket lit
       ("kit2_fin_brtype_cont/shots/00006_right.png", 0, 2),          # its Exposure Value lit
       ("kit2_fin_brtype_cont_img/shots/00007_right.png", 1, 2),      # its Number of Shots lit
       ("kit2_fin_brtype_cont_img/shots/00008_up.png", 1, 2),         # one Up on it: 5 Images
       ("kit2_fin_brtype_f_look/shots/00007_right.png", 0, 2),        # Single Bracket's Exposure Value
       ("kit2_fin_brtype_f_look/shots/00008_right.png", 1, 2),        # its Number of Shots
       ("kit2_fin_brtype_f_look/shots/00009_menu.png", None, 0),      # MENU in the fields: the option lit again
       ("kit2_fin_brtype_f_look2/shots/00007_down.png", None, 0),     # Focus Bracket lit
       ("kit2_fin_brtype_f_look2/shots/00008_right.png", 0, 4),       # its Step Width
       ("kit2_fin_brtype_f_look2/shots/00009_right.png", 1, 4),       # its Number of Shots' first digit
       ("kit2_fin_brtype_wbhi/shots/00009_right.png", None, 0)]       # White Balance Bracket: Hi, a second axis


@pytest.mark.parametrize("name, field, count", BRK)
def test_the_cameras_bracket_type_frames(name, field, count):
    s = screen.read(load(need(A1 / name)))
    assert s.kind == "dialog"
    assert s.field == field and len(s.boxes) == count
