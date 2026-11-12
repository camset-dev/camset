"""camlink's command lines (K-08, K-09): paths with spaces and Windows line ends arrive whole.

The Python side is tested against a stand-in camlink (fake_camlink.py) under a run folder whose path holds a space;
the C++ side by compiling kit/link/protocol.h, the parser camlink.cpp uses, with a small main (skipped without a
C++ compiler) and feeding it "\\r\\n" lines. Nothing here talks to a camera.
"""
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ROOT, provenance  # noqa: E402
from camkit.link import Link, quoted  # noqa: E402
from camkit.runs import Run  # noqa: E402
import fake_camlink  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fake_camlink.py"
# the stand-in, as fake_camlink.COMMAND starts it: -X utf8, which camkit needs on Windows
CAMLINK = [sys.executable, "-X", "utf8", str(FAKE)]


@pytest.fixture
def spaced(tmp_path, monkeypatch):
    run = Run("kit2 test", root=tmp_path / "First Last" / "my runs")
    log = tmp_path / "received.txt"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    monkeypatch.delenv("CAMSET_USB", raising=False)
    return run, log


def received(log: Path) -> list:
    return [ast.literal_eval(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_paths_with_spaces_arrive_whole(spaced):
    run, log = spaced
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        got = link.download("before")
        assert got.parent == run.dat and got.name == "00001_before.DAT" and got.exists()
        assert provenance.check(got, run.root)
        r = link.call("hello")
        shot = run.shots / "00002 osd frame.png"
        assert link.osd(shot) == shot
        sha = provenance.sha256(got)
        assert link._must(f"upload {quoted(got.resolve())} {sha}")["args"] == [str(got.resolve()), sha]
        odd = run.shots / 'a "quoted" C:\\path with spaces.png'
        assert link.osd(odd) == odd
        assert r["cmd"] == "hello"
    lines = received(log)
    assert lines[0] == f'@1 download {quoted(run.dat)} "00001_before"\n'.encode()          # each with its id
    assert all(raw.endswith(b"\n") and b"\r" not in raw for raw in lines)       # never "\r\n", on any OS
    assert lines[-1] == b"quit\n"


def test_upload_goes_through_provenance_and_quoting(spaced):
    run, log = spaced
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        got = link.download("start")
        sha = provenance.check(got, run.root)["sha256"]
        r = link.upload(got)
        assert r["args"] == [str(got.resolve()), sha] and r["sha256"] == sha
    # the line carries the SHA-256 the guard checked: camlink reads the file once and sends it only with that hash
    assert received(log)[-2] == f"@2 upload {quoted(got.resolve())} {sha}\n".encode()


def test_an_upload_line_without_the_checked_hash_is_refused(spaced):
    """Any upload line, whoever writes it, carries the SHA-256 of the download's bytes the guard checked: one with none,
    or with another, is refused before a byte goes out; a word after the path that is no SHA-256 is no command."""
    from camkit.link import LinkError
    run, log = spaced
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        got = link.download("start")
        with pytest.raises(LinkError, match="carries no SHA-256"):
            link.call(f"upload {quoted(got)}")
        with pytest.raises(LinkError, match="not the ones the SHA-256 on the line names"):
            link.call(f"upload {quoted(got)} {'0' * 64}")
        with pytest.raises(ValueError, match="not a SHA-256"):
            link.call(f"upload {quoted(got)} now")
    assert not [raw for raw in received(log) if b" upload " in raw]
    events = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in events].count("upload_refused") == 2


def test_a_camlink_that_does_not_take_the_hash_is_refused_when_the_link_opens(spaced, monkeypatch):
    """A camlink built before the hash (no "upload_sha256" in its ready line) refuses every upload line the kit now
    sends, so a run would change the camera and fail at its put-back. The link refuses to open instead, before any
    command goes out, saying how to rebuild it; one that says it takes the hash opens."""
    from camkit.link import LinkError
    run, log = spaced
    monkeypatch.setenv("FAKE_CAMLINK_READY_OMIT", "upload_sha256")
    link = Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False)
    with pytest.raises(LinkError, match=r"older than the kit.*python3 kit/setup\.py"):
        link.open()
    assert link.proc is None and received(log) == [b"quit\n"]          # nothing but the clean goodbye
    events = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in events][-2:] == ["link_refused", "link_close"]
    monkeypatch.delenv("FAKE_CAMLINK_READY_OMIT")
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as again:
        assert again.call("ping")["ok"]


@pytest.mark.parametrize("said", ["none", "0" * 64])          # "none": the reply carries no "sha256"
def test_an_upload_answered_without_the_checked_hash_is_not_taken_as_done(spaced, monkeypatch, said):
    """camlink's reply names the SHA-256 of the bytes it sent. A reply with none, or with another, means they were not
    checked against the kit's: Link.upload says so, and that the camera may have taken them, instead of returning."""
    from camkit.link import LinkError
    run, _ = spaced
    monkeypatch.setenv("FAKE_CAMLINK_UPLOAD_SHA256", said)
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        got = link.download("start")
        with pytest.raises(LinkError, match="may already have taken the file.*python3 kit/setup.py"):
            link.upload(got)
    events = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [e["kind"] for e in events].count("upload_unconfirmed") == 1


def test_a_file_swapped_after_the_check_is_not_sent(spaced, monkeypatch):
    """The guard checks the download's bytes; camlink opens the file again. A file written between the two used to be
    uploaded unchecked: now camlink reads it once, finds its SHA-256 is not the one on the line, sends nothing and
    answers "hash_mismatch", and Link.upload refuses with words that say what happened and what to do."""
    from camkit.link import LinkError
    run, log = spaced
    real = provenance.check

    def check_then_swap(path, root=None):
        entry = real(path, root)
        Path(path).write_bytes(b"written after the kit's check")            # what camlink will read
        return entry

    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        got = link.download("start")
        sha = provenance.sha256(got)
        monkeypatch.setattr(provenance, "check", check_then_swap)
        with pytest.raises(LinkError, match="something wrote this file while it was being sent"):
            link.upload(got)
    assert received(log)[-2] == f"@2 upload {quoted(got.resolve())} {sha}\n".encode()
    events = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    refused = [e for e in events if e["kind"] == "upload_refused"]
    assert len(refused) == 1 and refused[0]["reply"]["cause"] == "hash_mismatch"
    assert "upload it again: the kit checks it afresh" in refused[0]["why"]


def test_the_download_pickers_pass_over_an_upload_copy(tmp_path):
    """camlink uploads from a copy it writes beside the file (_camlink_upload_<pid>.DAT, kit/common/settings_file.h),
    removed however the command ends; one a crash leaves must never be taken for the newest download. The three
    places that take the newest or last .DAT of a dat/ folder skip camlink's prefix."""
    import os
    import re
    sys.path.insert(0, str(ROOT / "kit"))
    from writer.generic import newest_download
    dat = tmp_path / "dat"
    dat.mkdir()
    shutil.copy(fake_camlink.SAMPLE, dat / "00001_start.DAT")
    shutil.copy(fake_camlink.SAMPLE, dat / "_camlink_upload_4242.DAT")
    os.utime(dat / "00001_start.DAT", (1_000_000, 1_000_000))                   # the copy is the newer
    assert newest_download(tmp_path).name == "00001_start.DAT"
    prefix = re.search(r'"(_camlink_upload)"', (ROOT / "kit" / "link" / "camlink.cpp").read_text(encoding="utf-8"))
    assert prefix, "camlink names its upload copy"
    for rel, picker in (("kit/tools/upload_check.py", "downloads = "), ("kit/writer/generic.py", "files = sorted("),
                        ("kit/schema_update.py", "latest = camset_read(sorted(")):
        line = next(x for x in (ROOT / rel).read_text(encoding="utf-8").splitlines() if x.strip().startswith(picker))
        assert f'startswith("{prefix.group(1)}")' in line, rel


def test_quoted_rejects_line_breaks():
    with pytest.raises(ValueError):
        quoted("two\nlines")


LINES = [
    b'download "C:\\\\Users\\\\First Last\\\\camset\\\\runs\\\\kit2_pass2\\\\dat" "00001_before"\r\n',
    b'osd /Users/first last/runs/x/00002_osd.png\r\n',                  # the old unquoted rest of the line
    b'upload "/home/first last/runs/kit2 x/dat/00003_start.DAT"\r\n',
    b'setstr SetCopyright "a \\"b\\" c"\r\n',
    b'download "/tmp/a b" 00004_x\n',
    b'upload "no closing quote\r\n',
    b'upload "/home/first last/runs/kit2 x/dat/00003_start.DAT" 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\r\n',      # the kit's: the hash it checked
    b'upload /home/first last/x.DAT 0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF\n',                       # typed by hand, without quotes
    b'upload /home/first last/x.DAT 123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n',                           # 63 digits: part of the path
    b'upload "/a b/c.DAT" now\n',
    b'upload "/a b/c.DAT" 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef more\n',
]
WANT = [
    ["download", "C:\\Users\\First Last\\camset\\runs\\kit2_pass2\\dat", "00001_before"],
    ["osd", "/Users/first last/runs/x/00002_osd.png"],
    ["upload", "/home/first last/runs/kit2 x/dat/00003_start.DAT"],
    ["setstr", "SetCopyright", 'a "b" c'],
    ["download", "/tmp/a b", "00004_x"],
    None,
    ["upload", "/home/first last/runs/kit2 x/dat/00003_start.DAT", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"],
    ["upload", "/home/first last/x.DAT", "0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF"],
    ["upload", "/home/first last/x.DAT 123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"],
    None,
    None,
]


def test_the_stand_in_parses_as_documented():
    """The stand-in reads a line with the link's own parser (camkit.link.parse_command, which the guards read every
    command with): it must read each line as protocol.h does (the compiled test below)."""
    for raw, want in zip(LINES, WANT, strict=True):
        line = raw.decode()[:-1] if raw.endswith(b"\n") else raw.decode()
        if want is None:
            with pytest.raises(ValueError):
                fake_camlink.parse(line)
            continue
        cmd, args = fake_camlink.parse(line)
        assert [cmd, *args] == want, raw


MAIN = r'''
#include "protocol.h"
#include <cstdio>
#include <iostream>
#include <sstream>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
int main() {
#ifdef _WIN32
    // the bytes as they are, as on every other OS: in text mode Windows would turn stdin's "\r\n" into "\n" before the
    // parser sees it, and stdout's "\n" into "\r\n"
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    std::string line;
    while (protocol::readLine(std::cin, line)) {
        std::istringstream in(line);
        std::string cmd;
        const std::string id = protocol::command(in, cmd);
        std::string out = cmd;
        try {
            if (cmd == "download" || cmd == "setstr") {
                std::string first;
                protocol::word(in, first);
                out += "|" + first;
            }
            if (cmd == "upload") {
                std::string hash;
                out += "|" + protocol::pathAndHash(in, hash);
                if (!hash.empty()) out += "|" + hash;
            } else {
                out += "|" + protocol::rest(in);
            }
        } catch (const std::exception&) {
            out = cmd + "|error";
        }
        std::cout << id << "#" << out << "\n";
    }
}
'''
# a request's id ("@N") goes before the command; anything else that starts with "@" is no id
# an id comes back without its leading zeros ("@007" is 7, which is JSON; 007 is not), and an id with no command is
# still a request: camlink answers it with an error (camlink.cpp serve())
ID_LINES = [b'@17 osd "/a b/c.png"\r\n', b'@123456789 ping\n', b'@x1 ping\n', b'@ ping\n', b'@007 ping\n', b'@5\n',
            b'@000\r\n']
ID_WANT = [("17", ["osd", "/a b/c.png"]), ("123456789", ["ping", ""]), ("", ["@x1", "ping"]), ("", ["@", "ping"]),
           ("7", ["ping", ""]), ("5", ["", ""]), ("0", ["", ""])]


def test_camlink_parser_takes_quotes_crlf_and_ids(tmp_path):
    cxx = next((c for c in ("c++", "clang++", "g++") if shutil.which(c)), None)
    if not cxx:
        pytest.skip("no C++ compiler")
    src = tmp_path / "protocol_main.cpp"
    src.write_text(MAIN, encoding="utf-8")
    exe = tmp_path / "protocol_main"
    r = subprocess.run([cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "kit" / "link"), str(src),
                        "-o", str(exe)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    out = subprocess.run([str(exe)], input=b"".join(LINES + ID_LINES), capture_output=True, timeout=30).stdout.decode()
    got = [tuple(line.split("#", 1)) for line in out.split("\n")[:-1]]
    assert [(i, x.split("|")) for i, x in got] == \
        [("", w if w else ["upload", "error"]) for w in WANT] + ID_WANT


def test_the_stand_in_answers_ids_as_camlink_does(tmp_path):
    """"@007" is echoed as 7, an id with no command gets its one reply (an error), as camlink's serve() does."""
    lines = b"@007 ping\n@5\n@6 hello\r\nquit\n"
    out = subprocess.run(fake_camlink.COMMAND, input=lines, capture_output=True, timeout=60).stdout.decode()
    replies = [json.loads(x) for x in out.splitlines()][1:]               # after the ready line
    assert [(r["id"], r["ok"]) for r in replies] == [(7, True), (5, False), (6, True)]
    assert replies[0]["cmd"] == "ping" and "no command" in replies[1]["error"] and replies[2]["cmd"] == "hello"


def test_replies_are_matched_by_their_id_past_stray_lines(spaced, monkeypatch):
    """K-32: the SDK or a library printing on camlink's stdout, or a late reply to another request, no longer shifts
    every later reply onto the wrong command: each reply is matched by the id its command carried."""
    run, log = spaced
    monkeypatch.setenv("FAKE_CAMLINK_STRAY", "1")
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        assert link.call("hello")["cmd"] == "hello"
        assert link.call("ping")["cmd"] == "ping"
        assert link.press("up", screen="menu")["args"] == ["up", "60"]
        assert link.download("x").name == "00001_x.DAT"
    sent = received(log)
    assert [raw.split(b" ", 1)[0] for raw in sent[:4]] == [b"@1", b"@2", b"@3", b"@4"]
    events = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    stray = [e for e in events if e["kind"] == "stray_output"]
    assert len(stray) == 8 and {e["line"] for e in stray} == {"SDK: a line of its own on stdout",
                                                             json.dumps({"ok": True, "id": 999999})}
    assert [e["id"] for e in events if e["kind"] == "cmd"] == [1, 2, 3, 4]


def test_stderr_lines_of_any_shape_never_stop_the_link(spaced, monkeypatch, tmp_path):
    """camlink's stderr carries its events as objects; a library can print anything there. A line that parses as
    JSON but is no object ("0", "null"), or an object with the log's own keys, used to kill the thread that drains
    stderr (TypeError), after which camlink blocked on a full pipe and every reply stopped. 100 KB more after them
    must still be drained and the link answer."""
    run, _ = spaced
    lines = ["0", "null", "[1, 2]", json.dumps({"event": "note", "kind": "theirs", "t": 5})] + ["x" * 99] * 1000
    sent = tmp_path / "stderr_lines.json"          # 100 KB: more than Windows lets an environment variable hold
    sent.write_text(json.dumps(lines), encoding="utf-8")
    monkeypatch.setenv("FAKE_CAMLINK_STDERR_FILE", str(sent))
    import time
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        assert link.call("ping")["cmd"] == "ping"          # the stand-in wrote all 100 KB before its ready line
        assert link.events[:3] == [{"event": "text", "text": t} for t in ("0", "null", "[1, 2]")]

    def logged():
        events = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        return [e for e in events if e["kind"] == "sdk_event"]
    end = time.monotonic() + 10                              # the draining thread logs the rest as it goes
    while len(logged()) < len(lines) and time.monotonic() < end:
        time.sleep(0.05)
    sdk = logged()
    assert len(sdk) == len(lines)
    assert {"event": "note", "event_kind": "theirs", "event_t": 5}.items() <= sdk[3].items()


def test_a_config_without_the_cameras_address_says_what_to_set(spaced, monkeypatch):
    """No "camera_ip" in private/config.json and no address given: a sentence saying where to put it, not KeyError."""
    from camkit import ConfigMissing, link as L
    run, _ = spaced
    monkeypatch.setattr(L, "config", lambda required=True: {"eyes": "osd"})
    with pytest.raises(ConfigMissing, match="camera_ip"):
        Link(run, binary=CAMLINK, catch_signals=False)
    assert Link(run, usb=True, binary=CAMLINK, catch_signals=False).args[-1] == "--usb"


def test_once_camlink_has_exited_every_command_fails_at_once(spaced, monkeypatch):
    """The end of camlink's output used to be seen by one command only; every later one (the run's download, its
    restore) then waited its whole timeout, 90 s and 150 s, for a reply that could not come."""
    import time
    from camkit.link import LinkError
    run, _ = spaced
    monkeypatch.setenv("FAKE_CAMLINK_EXIT", "ping")
    link = Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False).open()
    try:
        with pytest.raises(LinkError, match="exited"):
            link.call("ping", timeout=20)
        t0 = time.monotonic()
        for line in ("hello", "get CameraOperatingMode", "props"):
            with pytest.raises(LinkError, match="exited"):
                link.call(line, timeout=60)
        assert time.monotonic() - t0 < 5
    finally:
        link.close()


# ---------------------------------------------------------------- one guarded choke point (K-14, K-26, K-38)

def test_every_command_goes_through_the_guards(spaced):
    """Link.call is the one way to camlink: a never button, a guarded one not allowed, a hold past the cap, a property
    that makes sound, light or motion (or is no live exposure), any text property, an upload that is no download and a
    command the kit does not send are refused before a byte goes out, whichever method or line sent them."""
    from camkit import safety
    from camkit.link import LinkError
    run, log = spaced
    stray = run.dir / "made_by_hand.DAT"
    stray.write_bytes(b"not the camera's")
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        for line in ("press c1", "press movie 60", "press c4 60 allowed", "press fn", "press up 5000", "press up 60 now",
                     "dial wheel x", "dial thumbnail 1", "set PreAF 1", "set TallyLampControlRed 1",
                     "set CameraButtonFunction 1310721", "set 0x5021 1", "set DriveMode 1", "set ShutterSpeed",
                     'setstr SetCopyright "x"', "setstr ImageID_String x", "format", "quit"):
            with pytest.raises(safety.Refused):
                link.call(line)
        with pytest.raises(safety.Refused):
            link.press("c7")
        with pytest.raises(safety.Refused):
            link.press("up", hold_ms=2001)
        with pytest.raises(safety.Refused):
            link.set("AudioSignals", 0)
        with pytest.raises(LinkError, match="not a camera download"):
            link.call(f"upload {quoted(stray)}")
        # what passes: a menu press, a guarded one the caller allows (marked so for camlink), the live exposure
        assert link.press("up", screen="menu")["args"] == ["up", "60"]
        assert link.press("fn", allow={"fn"}, screen="menu")["args"] == ["fn", "60", "allowed"]
        assert link.set("ShutterSpeed", 65786)["args"] == ["ShutterSpeed", "65786"]
        assert link.dial("wheel", -2, screen="menu")["args"] == ["wheel", "-2"]
    sent = b"".join(received(log))
    for word in (b"c1", b"movie", b"c4", b"5000", b"PreAF", b"Tally", b"CameraButton", b"0x5021", b"DriveMode",
                 b"setstr", b"format", b"made_by_hand"):
        assert word not in sent, word
    events = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert sum(e["kind"] == "cmd_refused" for e in events) >= 20


# spellings of a key that camlink's parser reads as the key itself (it drops spaces and quotation marks) or that a
# check made on the name as given would not see as that key: each is refused before a byte goes out
NOT_KEY_NAMES = [" down", "down ", "down\t", '"down"', "'down'", "“down”", "Down", "DOWN", "dоwn", "ｄｏｗｎ", "do\u200bwn",
                 " right", "Enter", '"c4"', "c4 ", "C4", "", "do wn"]


@pytest.mark.parametrize("name", NOT_KEY_NAMES)
def test_a_key_not_written_as_the_guards_read_it_is_refused(spaced, name):
    from types import SimpleNamespace
    from camkit import safety
    run, log = spaced
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        with pytest.raises(safety.Refused, match="not written as the guards read it"):
            link.press(name, allow={"c4", "C4", name}, screen=SimpleNamespace(kind="menu"), cleanup=True)
        with pytest.raises(safety.Refused, match="not written as the guards read it"):
            link.dial(name, 1)
    assert not [raw for raw in received(log) if b"press" in raw or b"dial" in raw]


def test_every_key_the_kit_names_still_goes_out(spaced):
    """The rule only adds refusals: every menu input goes out as before, a guarded one where it is allowed, and every
    key name a press or dial call in kit/ writes out is one the rule accepts."""
    import re
    from types import SimpleNamespace
    from camkit import safety
    run, _ = spaced
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        for name in sorted(safety.MENU_INPUTS):
            assert link.press(name, screen=SimpleNamespace(kind="menu"))["args"][0] == name
        for name in sorted(safety.GUARDED_INPUTS):
            assert link.press(name, allow={name}, screen=SimpleNamespace(kind="menu"))["args"] == [name, "60", "allowed"]
        assert link.dial("wheel", -1, screen="menu")["args"] == ["wheel", "-1"]
    for name in safety.MENU_INPUTS | safety.GUARDED_INPUTS | safety.NEVER_INPUTS:
        assert safety.name_refused(name) == "", name
    written = set()
    for p in (ROOT / "kit").rglob("*.py"):
        if not {"tests", "sdk", "vendor"} & set(p.parts):
            written |= set(re.findall(r"\.(?:press|dial)\(\s*[\"']([^\"']*)[\"']", p.read_text(encoding="utf-8")))
    assert written and not {w: safety.name_refused(w) for w in written if safety.name_refused(w)}


def test_a_stop_ends_every_change_but_the_cleanup_and_the_reads(spaced):
    from camkit.link import StopRequested
    run, log = spaced
    with Link(run, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link:
        (run.dir / "STOP").write_text("", encoding="utf-8")
        for send in (lambda: link.press("down", screen="menu"), lambda: link.dial("wheel", 1, screen="menu"),
                     lambda: link.set("FNumber", 800), lambda: link.call("press up", screen="menu")):
            with pytest.raises(StopRequested, match="asks the run to stop"):
                send()
        assert link.press("menu", cleanup=True)["ok"]                  # cancelling a dialog after a stop
        got = link.download("after-stop")                                # and the run's restore: download, upload
        assert link.upload(got)["ok"]
    assert b"press down" not in b"".join(received(log))


def test_a_stop_file_left_from_before_is_said_and_refuses_the_first_press(spaced, capsys):
    from camkit.link import StopRequested
    run, _ = spaced
    (run.dir / "STOP").write_text("", encoding="utf-8")
    again = Run(run.dir.name, root=run.root)
    assert "from an earlier stop" in capsys.readouterr().err
    with Link(again, ip="192.0.2.10", binary=CAMLINK, catch_signals=False) as link, \
            pytest.raises(StopRequested, match="before this run started"):
        link.press("menu")


def test_never_set_properties_and_the_exposure_the_kit_sets():
    from camkit import safety
    for name in ("PreAF", "CrDeviceProperty_PreAF", "FocusOperationWithInt16", "ImageStabilizationSteadyShot",
                 "AFIlluminator", "TallyLampControlGreen", "FlashMode", "AudioSignalsVolume", "PlaybackVolumeSettings",
                 "SetCopyright", "SetPhotographer", "LanguageSetting", "DateTime_Settings", "USBPowerSupply",
                 "WakeOnLAN", "CameraButtonFunction", "CameraLeverFunction", "S1", "RecorderStartMain", "0x5021", ""):
        assert safety.never_property(name), name
    assert safety.never_property("PreAF").startswith(safety.MOTION)
    for name in safety.SET_PROPERTIES | {"WhiteBalance", "FocusMode", "DriveMode"}:
        assert safety.never_property(name) is None, name
    with pytest.raises(safety.Refused, match="not one the kit sets"):
        safety.check_property("DriveMode")
    safety.check_property("CrDeviceProperty_FNumber")


def test_the_cpp_programs_compile_the_same_lists():
    """kit/common/never_touch.h is written from camkit/safety.py (build_docs.py) and current; guards_test.cpp checks
    that the C++ side reads it as the kit does."""
    sys.path.insert(0, str(ROOT / "kit" / "tools"))
    import build_docs
    from camkit import safety
    header = (ROOT / "kit" / "common" / "never_touch.h").read_text(encoding="utf-8")
    assert header == build_docs.never_touch_h()
    for b in safety.NEVER_INPUTS | safety.GUARDED_INPUTS:
        assert f'"{b}"' in header


def compiled(tmp_path, name: str) -> Path:
    """kit/common/<name>.cpp built with -Wall -Wextra -Werror (skipped without a C++ compiler)."""
    cxx = next((c for c in ("c++", "clang++", "g++") if shutil.which(c)), None)
    if not cxx:
        pytest.skip("no C++ compiler")
    exe = tmp_path / name
    r = subprocess.run([cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "kit" / "common"),
                        str(ROOT / "kit" / "common" / f"{name}.cpp"), "-o", str(exe)],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    return exe


def test_the_cpp_guards(tmp_path):
    r = subprocess.run([str(compiled(tmp_path, "guards_test"))], capture_output=True, text=True, timeout=60, cwd=ROOT)
    assert r.returncode == 0, r.stderr
