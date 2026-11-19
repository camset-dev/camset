"""The engineering review of 2026-11-18, track 2 (the mapping pipeline, the provers, the readers): each finding fixed
here has its test, written first to show it. No camera: the provers run against fakes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ------------------------------------------------------------------------------------------------ finding 2 (B1)

def test_the_report_never_takes_a_lost_decimal_point_or_fraction_slash_for_agreement():
    """pass2_report compared labels with norm(), which drops "." and "/": 1.3" and 13", F1.1 and F11, 1/250 and 1250
    were one label, so swapped labels passed as "agrees" and two such proofs merged at one index."""
    import pass2_report as R
    verdict, notes = R.judge({'1.3"': 5, '13"': 9, "F1.1": 1, "F11": 2}, {5: '13"', 9: '1.3"', 1: "F11", 2: "F1.1"})
    assert verdict == "conflict" and sorted(n["value"] for n in notes if n["kind"] == "conflict") == [1, 2, 5, 9]
    assert R.judge({'1.3"': 5}, {5: '13"'})[0] != "agrees"
    assert R.judge({"1/250": 7}, {7: "1250"})[0] != "agrees"
    assert R.option_key({"index": 5, "label": '13"'}, {5: {"label": '1.3"'}}) != 5
    assert R.option_key({"index": 5, "label": "1/250"}, {5: {"label": "1250"}}) != 5
    assert not R.alike("F1.1", "F11") and not R.alike('2.5"', '25"') and not R.alike("1/250", "1250")
    # what norm's leniency was for still holds: the same label, its case, spacing, a dot, a sign spelled out
    assert R.judge({"5 Img.": 3, "-(minus) -> 0 -> +(plus)": 4}, {3: "5 img", 4: "-→0→+"}) == ("agrees", [])
    assert R.option_key({"index": 2, "label": "ISO 100"}, {2: {"label": "ISO100"}}) == 2
    assert R.alike("FINE", "FINE Fine") and R.alike("4:3", "4:3 4:3") and R.alike("F1.1", "F1.1")
