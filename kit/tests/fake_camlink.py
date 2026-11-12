"""A stand-in for kit/link/build/camlink in the tests: its command-line protocol (kit/link/protocol.h), no camera.

    Link(run, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False)
    # COMMAND is [sys.executable, "-X", "utf8", "kit/tests/fake_camlink.py"]

Prints camlink's ready line, then answers every command with {"ok": true, "cmd", "args"}, the arguments parsed as
protocol.h parses them. download DIR NAME writes NAME.DAT (a copy of the ILCE-1M2 definition's sample,
editor/definitions/ILCE-1M2_fw4.00.DAT; for a NAME ending "_after", $FAKE_CAMLINK_AFTER when set) into DIR, as the
camera would. props answers with $FAKE_CAMLINK_PROPS (a JSON list of {"name", "text"}; none without it) and its
count, or, with $FAKE_CAMLINK_PROPS_FAIL set, as camlink answers when the SDK's read fails ({"ok": false, "error":
"GetDeviceProperties failed"}); get NAME with $FAKE_CAMLINK_GET's entry for NAME merged in (a JSON object {name:
{"current": ...}}), and a NAME it holds no entry for as camlink answers both a property the body does not list and a
listed one whose read fails ({"ok": false, "error": "unknown property NAME"}). A line's leading "@N" (the
request's id, protocol::command) is echoed as "id": N. With $FAKE_CAMLINK_STRAY set, every reply comes after two
stray lines, as an SDK or a library may print them: a line of text and a reply with another id. Every line
received, as raw bytes, goes to the file $FAKE_CAMLINK_LOG (one repr per line). $FAKE_CAMLINK_STDERR (a JSON list of
lines; $FAKE_CAMLINK_STDERR_FILE names a file holding that list instead, for more than Windows lets one environment
variable carry, 32767 characters) is written to stderr before the ready line, as camlink's events and a library's prints would be; with
$FAKE_CAMLINK_EXIT naming a command, the stand-in exits on it without a reply, as a camlink that crashed. A request
id is read as camlink reads it: "@007" echoes 7, and an id with no command gets an error reply. upload PATH [SHA256]
reads the file once, as camlink does, and answers with its "sha256"; one whose bytes do not have the SHA256 given
gets camlink's refusal ({"ok": false, "cause": "hash_mismatch"}), and a file that is not there "no such file". The
ready line says "upload_sha256": true, as camlink's does; $FAKE_CAMLINK_READY_OMIT (names, comma-separated) leaves
those out of it, as an older camlink would, and $FAKE_CAMLINK_UPLOAD_SHA256, when set, is what a sent upload's reply
gives as its "sha256" instead ("none": no "sha256" at all; Windows passes no variable set to the empty string on to
a child, so the empty value cannot say it), as a camlink that did not check the bytes would.

Start it as COMMAND does: with -X utf8, since it imports camkit, which on Windows needs Python's UTF-8 mode, and a
"-X utf8" given to the test run is not passed on to the processes it starts (PYTHONUTF8=1 is).
"""
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# protocol.h's reading of a line, as the link's own guards read it (test_link_protocol ties both to protocol.h)
from camkit.link import parse_command as parse  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[2] / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"
COMMAND = [sys.executable, "-X", "utf8", str(Path(__file__).resolve())]       # Link(..., binary=COMMAND)


def main():
    log = os.environ.get("FAKE_CAMLINK_LOG")
    out = sys.stdout
    lines = os.environ.get("FAKE_CAMLINK_STDERR")
    if os.environ.get("FAKE_CAMLINK_STDERR_FILE"):
        lines = Path(os.environ["FAKE_CAMLINK_STDERR_FILE"]).read_text(encoding="utf-8")
    for line in json.loads(lines or "[]"):
        sys.stderr.write(line + "\n")
    sys.stderr.flush()
    ready = {"ok": True, "ready": "ILCE-1M2", "connection": "lan 192.0.2.10", "login": "none", "upload_sha256": True}
    omit = {k.strip() for k in os.environ.get("FAKE_CAMLINK_READY_OMIT", "").split(",")}
    out.write(json.dumps({k: v for k, v in ready.items() if k not in omit}) + "\n")
    out.flush()
    for raw in sys.stdin.buffer:
        if log:
            with open(log, "a", encoding="utf-8") as f:
                f.write(repr(raw) + "\n")
        line = raw.decode("utf-8")
        line = line[:-1] if line.endswith("\n") else line
        line = line[:-1] if line.endswith("\r") else line
        # protocol::command: "@" and 1-18 digits before the command, echoed as a number ("@007" as 7)
        rid = re.match(r"@(\d{1,18})(?=[ \t]|$)", line)
        line = line[rid.end():] if rid else line
        rid = {"id": int(rid.group(1))} if rid else {}
        if os.environ.get("FAKE_CAMLINK_STRAY"):
            out.write("SDK: a line of its own on stdout\n" + json.dumps({"ok": True, "id": 999999}) + "\n")
        if rid and not line.strip():                    # every request gets its one reply, as camlink's serve()
            out.write(json.dumps({"ok": False, "error": "no command after the request's id", **rid}) + "\n")
            out.flush()
            continue
        try:
            cmd, args = parse(line)
        except ValueError as e:
            out.write(json.dumps({"ok": False, "error": f"bad arguments: {e}", **rid}) + "\n")
            out.flush()
            continue
        if cmd == "quit":
            return
        if cmd == os.environ.get("FAKE_CAMLINK_EXIT"):
            sys.exit(3)
        reply = {"ok": True, "cmd": cmd, "args": args, **rid}
        if cmd == "download":
            dst = Path(args[0]) / f"{args[1]}.DAT"
            dst.parent.mkdir(parents=True, exist_ok=True)
            after = os.environ.get("FAKE_CAMLINK_AFTER")
            shutil.copy(after if after and args[1].endswith("_after") else SAMPLE, dst)
            reply.update(path=str(dst), bytes=dst.stat().st_size)
        elif cmd == "osd":
            reply.update(path=args[0])
        elif cmd == "upload":
            reply.update(upload(*args))
        elif cmd == "props":
            props = json.loads(os.environ.get("FAKE_CAMLINK_PROPS") or "[]")
            # camlink's cmdProps: the list and its count, or its one error when the SDK's read fails
            reply.update({"ok": False, "error": "GetDeviceProperties failed"} if os.environ.get("FAKE_CAMLINK_PROPS_FAIL")
                         else {"count": len(props), "props": props})
        elif cmd == "get":
            known, name = json.loads(os.environ.get("FAKE_CAMLINK_GET") or "{}"), args[0] if args else ""
            # a property it was not given is one the body does not list, answered as camlink's cmdGet answers it
            reply.update(known.get(name, {"ok": False, "error": f"unknown property {name}"}))
        out.write(json.dumps(reply) + "\n")
        out.flush()


def upload(path, expected=""):
    """camlink's cmdUpload, without a camera: the file read once, its bytes' SHA-256 compared with the one given."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return {"ok": False, "error": f"no such file {path}"}
    digest = hashlib.sha256(data).hexdigest()
    if expected and expected.lower() != digest:
        return {"ok": False, "cause": "hash_mismatch",
                "error": f"not sent: these are not the bytes whose SHA-256 the upload named (theirs is {digest}, not "
                         f"{expected.lower()}): the file was written after it was checked"}
    said = os.environ.get("FAKE_CAMLINK_UPLOAD_SHA256")
    if said is None:
        return {"result": "read ok", "sha256": digest}
    return {"result": "read ok", **({"sha256": said} if said and said != "none" else {})}


if __name__ == "__main__":
    main()
