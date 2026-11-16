"""drive.py: enter!:regex, Enter vouched by the operator when nothing lit can be read (2026-11-09). Made-up screens."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import drive  # noqa: E402

MR = "Mr Memory 1 2 M1 M2 M3 M4 MENU OK"               # the MR Memory slots: nothing lit wide enough to read
TITLED = "Camera Set. Memory 1 2 3 M1 M2 M3 M4 MENU OK"  # the same with the row's own name in the title


def decide(p, lit, text, kind="unknown", confirm=False, allow=(), consent=""):
    """press_decision as main() calls it, after the press arguments were checked."""
    assert not drive.press_args_refused([p]), p
    key = drive.parse_press(p)[0]
    return drive.press_decision(p, key, lit, text, kind, confirm, allow, consent=consent)


MEMORY = "--allow 'Camera Set. Memory'"            # memreg_run's and framepos_run's consent to answer the slot screen


def test_plain_enter_is_refused_when_nothing_lit_can_be_read():
    why, vouched = decide("enter:memory", "", MR)
    assert "nothing lit" in why and not vouched


def test_the_refusal_of_an_unreadable_lit_text_says_how_the_person_vouches():
    """Its words say what the person does (2026-11-15, an Enter on Exposure Comp.'s slider refused): where they know
    what Enter does on that screen, --press 'enter!:REGEX' vouches for it. The check itself is unchanged."""
    for kind in ("slider", "unknown", "list"):
        why = drive.press_refused("enter", "", "Exposure Comp. -3 0 +3", kind)
        assert why.startswith("nothing lit can be read, so the button under the cursor is unknown"), why
        assert "--press 'enter!:REGEX' vouches for it" in why and not why.endswith("."), why


def test_vouched_enter_goes_ahead_where_nothing_lit_can_be_read_and_says_so():
    """Since 2026-11-14 the MR Memory slots, read as no known kind, take no Enter by their shape (safety.enter_refused):
    a vouch lifts the unreadable lit text alone, and the Enter goes with --confirm, the owner's word, or a prover's
    --allow for its own row (press_refused's consent)."""
    assert "no known kind" in decide("enter!:memory", "", MR)[0] or "'unknown'" in decide("enter!:memory", "", MR)[0]
    assert decide("enter!:memory", "", MR, confirm=True) == ("", True)
    assert decide("enter!:memory", "", MR, consent=MEMORY) == ("", True)
    assert drive.parse_press("enter!:memory")[0] == "enter"


def test_vouched_enter_is_only_vouched_when_nothing_lit_was_read():
    assert decide("enter!:memory", "M2", MR, confirm=True) == ("", False)     # a lit text read: no vouching
    assert decide("enter!:memory", "M2", MR)[0]                    # and the screen's shape still asks its word
    assert decide("enter!:memory", "Format", MR)[0]                # and the usual refusals


def test_vouched_enter_needs_enter_and_a_regex():
    assert drive.press_args_refused(["enter!"])
    assert drive.press_args_refused(["right!:x"])
    assert drive.press_args_refused(["enter!@200:x"])


def test_no_vouching_on_a_screen_whose_enter_opens_a_row():
    for kind in ("menu", "submenu", "tiles", "shooting"):
        why, vouched = decide("enter!:memory", "", MR, kind)
        assert why and not vouched, kind


def test_no_vouching_on_a_screen_that_reads_nothing():
    # a regex such as ".*" matches the blank text too, and screen_refused has nothing to judge there: fail closed
    for text in ("", "   ", " | - ", None):
        for p in ("enter!:.*", "enter!:^$", "ms_enter!:.*"):
            why, vouched = decide(p, "", text)
            assert "nothing on the screen" in why and not vouched, (p, text)
    assert drive.press_refused("enter", "", "", "unknown", vouched=True)


def test_no_vouching_on_a_screen_naming_a_credential_whatever_is_allowed():
    for text in ("Network Access Authen. Info Wi-Fi Direct Info. MENU OK", "Wi‑Fi Direct Info. SSID MENU OK",
                 "Password MENU OK"):
        why, vouched = decide("enter!:menu", "", text, allow=("Access Authen. Info", "Wi-Fi Direct Info."))
        assert why and not vouched, text


def test_no_vouching_on_a_screen_naming_the_cards_or_a_never_open_row():
    for text in ("Format Slot 1 OK", "Delete All MENU OK", "Fоrmat Slot 2 OK", "Screen Reader On MENU OK",
                 "Setting Reset MENU OK", "Pre-AF On MENU OK"):
        why, vouched = decide("enter!:ok", "", text)
        assert why and not vouched, text


def test_a_name_the_run_was_allowed_lifts_only_its_own_words_on_the_screen():
    assert decide("enter!:memory", "", TITLED)[0], "an action's name on the screen, not allowed"
    assert decide("enter!:memory", "", TITLED, allow=("Camera Set. Memory",), consent=MEMORY) == ("", True)
    assert decide("enter!:memory", "", TITLED + " Delete", allow=("Camera Set. Memory",))[0]


def test_vouched_enter_keeps_the_other_refusals():
    assert decide("enter!:memory", "Initialize", MR)[0]
    assert decide("enter!:ok", "", "Reset Network Set. OK")[0]
    assert decide("enter!:sure", "", "Are you sure? Yes No")[0]
    assert decide("enter!:sure", "", "Are you sure? Yes No", confirm=True) == ("", True)
