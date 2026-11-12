"""The publish guard (K-13, S-05): generic leaks, force-added paths, Sony's files by name, binaries, links, images'
metadata, and paths git would quote.

The made-up values are put together at run time, so this file itself holds none of what the guard refuses.
"""
import json
import os
import shutil
import stat
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_public as C  # noqa: E402


def mac(sep=":", pairs=(0x5C, 0x12, 0x34, 0x56, 0x78, 0x9A)):
    return sep.join(f"{x:02x}" for x in pairs)


def ip(*parts):
    return ".".join(map(str, parts))


@pytest.mark.parametrize("text", [mac(), mac("-").upper(), "{}{}.{}{}.{}{}".format(*(f"{x:02x}" for x in
                                  (0x5C, 0x12, 0x34, 0x56, 0x78, 0x9A))), mac(pairs=(0x58, 0x18, 0x62, 1, 2, 3))])
def test_any_mac_notation_and_prefix(text):
    assert [k for k, _ in C.leaks(f"camera at {text} today")] == ["a MAC address"]


def test_placeholders_pass():
    for t in ("00:11:22:33:44:55", "0a-1b-2c-3d-4e-5f", "AA:BB:CC:DD:EE:FF", ip(192, 168, 1, 50), ip(127, 0, 0, 1),
              ip(192, 0, 2, 10), ip(203, 0, 113, 7), "serial: 1234567", "noreply" + "@anthropic.com",
              "/Users/first/camset", "C:\\Users\\First\\camset", "version 1.2.3.4", "00:00:12"):
        assert C.leaks(t) == [], t


@pytest.mark.parametrize("text,kind", [
    (ip(10, 1, 2, 3), "a private network address"), (ip(172, 20, 0, 9), "a private network address"),
    (ip(192, 168, 7, 44), "a private network address"), (ip(169, 254, 3, 3), "a private network address"),
    ("Serial" + "Number = 4419" + "233", "a serial number"), ('"serial"' + ': "AB55' + '01234"', "a serial number"),
    ("alex" + "@" + "mail.test", "an e-mail address"), ("/Users/" + "alex/camset", "a home folder"),
    ("/home/" + "alex/runs", "a home folder"),
])
def test_generic_leaks(text, kind):
    assert kind in [k for k, _ in C.leaks(text)]


def test_force_added_paths_and_sonys_files():
    found = C.path_problems(["runs/kit2_pass2/dat/00001_before.DAT", "private/config.json", "kit/sdk/README.md",
                             "kit/sdk/SimpleCli/app/CRSDK/CrDeviceProperty.h", "docs/images/x.png"],
                            ["lut/some_pack.cube"])
    text = "\n".join(found)
    assert "runs/kit2_pass2/dat/00001_before.DAT: runs/ is never published" in text
    assert "private/config.json: private/ is never published" in text
    assert "kit/sdk/README.md" not in text and "docs/images/x.png" not in text
    assert "lut/some_pack.cube: .gitignore ignores it" in text
    for path in ("third/CrDeviceProperty.h", "x/ICrCameraObjectInfo.h", "x/IDeviceCallback.h", "x/PropertyValueTable.h",
                 "x/libCr_PTP_IP.dylib", "x/libmonitor_protocol.so", "x/CrAdapter/libCr_PTP_USB.so",
                 "x/Camera_Remote_SDK_Readme_v2.02.00.pdf", "x/CrSDK_API_Reference_v2.02.00.zip", "x/RemoteCli.zip",
                 "x/SimpleCli/app/CrDebugString.cpp", "x/RemoteSampleApp_IM_v2.02.00.pdf"):
        assert C.sony_sdk(path), path
    for path in ("kit/link/camlink.cpp", "kit/link/protocol.h", "kit/common/camera_net.h", "docs/PORTING.md",
                 "kit/camkit/crawl.py", "editor/src/camset.rs"):
        assert not C.sony_sdk(path), path


def png_with_text(text: str) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"\x00\x00\x00\x00"                                   # one 1x1 RGB pixel row
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"tEXt", b"Comment\x00" + text.encode()) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_binaries_are_read_for_strings_and_kept_to_the_list(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "docs" / "images").mkdir(parents=True)
    (tmp_path / "runs").mkdir()
    (tmp_path / "docs" / "images" / "ok.png").write_bytes(png_with_text("made with care"))
    (tmp_path / "docs" / "images" / "leak.png").write_bytes(png_with_text("camera " + mac()))
    (tmp_path / "frame.png").write_bytes(png_with_text("menu"))
    found = C.content_problems(["docs/images/ok.png", "docs/images/leak.png", "frame.png"], set(), set())
    text = "\n".join(found)
    assert "docs/images/ok.png" not in text
    assert "docs/images/leak.png: holds a MAC address" in text
    assert "frame.png: a binary file outside the published images" in text


def test_private_strings_and_home_addresses(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "private").mkdir()
    home = ip(192, 168, 7, 21)
    (tmp_path / "private" / "config.json").write_text(json.dumps({"camera_ip": home, "private_strings": ["Quentin Example"]}),
                                                      encoding="utf-8")
    addresses, owner = C.private_tokens()
    assert addresses == {home} and owner == {"Quentin Example"}
    (tmp_path / "notes.md").write_text(f"by quentin example, at {home}", encoding="utf-8")
    text = "\n".join(C.content_problems(["notes.md"], addresses, owner))
    assert "home network address" in text and "owner's name" in text


def v6(*groups) -> str:
    """An IPv6 address from its groups, written in full."""
    return ":".join(f"{g:x}" for g in groups)


@pytest.mark.parametrize("text,kind", [
    (v6(0xfe80, 0, 0, 0, 0x1c2b, 0x3d4e, 0x5f60, 0x7182), "a private network address"),       # link-local, a real id
    (v6(0xfd12, 0x3456, 0x789a, 0, 0, 0, 0, 0x10), "a private network address"),               # unique local
    (v6(0xfe80, 0, 0, 0, 0x1c2b, 0x3d4e, 0x5f60, 0x7182) + "%en0", "a private network address"),
    (v6(0x2a02, 0x1210, 0x1234, 0, 0x5e12, 0x34ff, 0xfe56, 0x789a), "a MAC address (an IPv6 address made from it)"),
    ("[" + v6(0xfd00, 0xabcd, 0, 0, 0, 0, 0, 0x99) + "]:8642", "a private network address"),
    ("mac" + ": " + mac(""), "a MAC address"), ('"MacAddress"' + ': "' + mac("").upper() + '"', "a MAC address"),
    (ip(192, 168, 1, 5).replace(".1.", ".001."), "a private network address"),                  # leading zeros
    ("S/N" + ": 4419" + "233", "a serial number"), ("SN" + "=4419" + "233", "a serial number"),
    ("Serial #" + "4419" + "233", "a serial number"),
    ("C:/Users/" + "alex/camset", "a home folder"), ("c:\\users\\" + "alex", "a home folder"),
    ("D:/USERS/" + "Bob", "a home folder"), ("/mnt/c/users/" + "alex", "a home folder"),
    ("cd /users/" + "alex/camset", "a home folder"), ("file:/Users/" + "alex", "a home folder"),
    ("alex+cam" + "@" + "mail.isp.test", "an e-mail address"),
    # a MAC right after a label or a name that ends in a hex digit, as HEAD refused it (review 1)
    ("mac:" + mac(), "a MAC address"), ("MAC:" + mac().upper(), "a MAC address"), ("bssid:" + mac(), "a MAC address"),
    ("uid:" + mac(), "a MAC address"), ("ILCE-1M2-" + mac("-").upper(), "a MAC address"),
    ("camera-" + mac("-"), "a MAC address"), (mac() + "-dev", "a MAC address"),
    ("wifi_mac" + "=" + mac(""), "a MAC address"),
    # an IPv6 address after a label's colon, before a sentence's colon or full stop
    ("addr:" + v6(0xfe80, 0, 0, 0, 0x1c2d, 0x3e4f, 0x5061, 0x7a8b), "a private network address"),
    ("ip:" + v6(0xfd12, 0x3456, 0x789a, 0, 0, 0, 0, 1), "a private network address"),
    ("at " + v6(0xfe80, 0, 0, 0, 0x1c2d, 0x3e4f, 0x5061, 0x7a8b) + ": the camera", "a private network address"),
    ("at " + v6(0xfe80, 0, 0, 0, 0x1c2d, 0x3e4f, 0x5061, 0x7a8b) + ".", "a private network address"),
    ("C:/home/" + "alex/camset", "a home folder"),
])
def test_more_notations_are_refused(text, kind):
    assert kind in [k for k, _ in C.leaks(text)], C.leaks(text)


@pytest.mark.parametrize("text", [
    "[fe80::1]:8642", "fe80::", "::1", v6(0x2001, 0xdb8, 1, 2, 0xaaaa, 0, 0, 1), "std::string and Self::Foo",
    "x[1::2]", "12:34:56", "Ok::Value and Rc::new(x)",
    v6(0x2001, 0xdb8, 0, 0, 0x211, 0x22ff, 0xfe33, 0x4455),          # made from the placeholder 00:11:22:33:44:55
    v6(0x2001, 0xdb8, 0, 0, 0x200, 0x5eff, 0xfe00, 0x5301),          # made from RFC 7042's documentation MAC
    "fc00::/7", "fd00::/8", "fd00::1", "fd00::",                     # unique local with the zero network id
    v6(0xfe80, 0, 0, 0, 0x200, 0x5eff, 0xfe00, 0x5301),             # link-local, made from a placeholder MAC
    v6(0xfe80, 0, 0, 0, 0x211, 0x22ff, 0xfe33, 0x4455) + "%en0", "api:/users/list",
    "00-00-5E-00-53-01", "mac" + ": " + "001122334455", "hmac: " + mac(""), "tomac=" + mac(""),
    "a test's number " + "1234567" + "89012", "isn" + ": 4419" + "233",
    "SN: 1234567", "https://api.github.com/users/" + "alex", "C:/Users/First/camset", "c:\\users\\you",
    "alex" + "@" + "mail.example.com", "no-reply" + "@github.com", "::ffff:" + ip(192, 0, 2, 1),
])
def test_placeholders_and_lookalikes_pass(text):
    assert C.leaks(text) == [], text


def test_what_a_finding_shows():
    """A finding shows the address or the folder as written: a zone without the sentence's full stop after it, a
    Windows folder from its drive letter, a macOS one after a word's colon whole."""
    real6 = v6(0xfe80, 0, 0, 0, 0x1c2d, 0x3e4f, 0x5061, 0x7a8b) + "%en0"
    assert [w for _, w in C.leaks(f"at {real6}.")] == [real6]
    assert [w for _, w in C.leaks("C:/Users/" + "alex/x")] == ["C:/Users/" + "alex"]
    assert [w for _, w in C.leaks("file:/Users/" + "alex/x")] == ["/Users/" + "alex"]


def test_a_home_address_is_a_unicast_one_of_the_owners(tmp_path, monkeypatch):
    """private/config.json's addresses are the owner's, but not the docs' placeholders an owner kept from the
    example, nor a netmask or 0.0.0.0; its IPv6 addresses count too."""
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "private").mkdir()
    real6 = v6(0x2a02, 0x1210, 0x1234, 0, 0, 0, 0, 0x22)
    (tmp_path / "private" / "config.json").write_text(json.dumps(
        {"camera_ip": ip(10, 0, 7, 21), "reader": f"http://{ip(192, 168, 1, 100)}:8080", "netmask": ip(255, 255, 255, 0),
         "any": ip(0, 0, 0, 0), "v6": f"[{real6}]"}), encoding="utf-8")
    home, _ = C.private_tokens()
    assert home == {ip(10, 0, 7, 21), real6.replace(":0:0:0:0:", "::")}
    (tmp_path / "notes.md").write_text(f"the reader at {ip(192, 168, 1, 100)}, a /24 is {ip(255, 255, 255, 0)}",
                                       encoding="utf-8")
    assert C.content_problems(["notes.md"], home, set()) == []
    (tmp_path / "v6.md").write_text(f"the camera at {real6}", encoding="utf-8")
    assert C.content_problems(["v6.md"], home, set()) == ["v6.md: holds a home network address from private/config.json"]
    (tmp_path / "private" / "config.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit, match="not valid JSON"):
        C.private_tokens()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A git repository of its own as the guard's root: nothing private, no definitions."""
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(C, "ROOT", tmp_path)
    return tmp_path


def test_a_name_git_would_quote_is_read_as_it_is(repo):
    """git quotes a path with a non-ASCII letter (core.quotePath): read that way, a name with an accented letter in
    private/ did not start with private/, café.md was never opened and a .DAT name ended in a quote. The guard reads
    git's -z lists."""
    (repo / "private").mkdir()
    (repo / "private" / "données.json").write_text("{}", encoding="utf-8")
    (repo / "notes_café.md").write_text(f"the camera at {mac()}", encoding="utf-8")
    (repo / "data").mkdir()
    (repo / "data" / "réglages.DAT").write_bytes(b"SONY1\0\0")
    subprocess.run(["git", "add", "-f", "."], cwd=repo, check=True)
    text = "\n".join(C.problems(everything=True))
    assert "private/" + "données.json: private/ is never published" in text
    assert "notes_café.md: holds a MAC address" in text
    assert "data/réglages.DAT: a settings file, and no definition names it" in text
    assert "data/réglages.DAT: a binary file outside the published images" in text


def test_no_git_no_pass(tmp_path, monkeypatch):
    """Outside a repository git lists nothing: the guard stops rather than pass on an empty list."""
    monkeypatch.setattr(C, "ROOT", tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    with pytest.raises(SystemExit, match="git ls-files -z failed"):
        C.git("ls-files", "-z")


def test_a_link_is_read_as_its_target_name(tmp_path, monkeypatch):
    """git publishes a link's target name, never the file behind it."""
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    try:
        os.symlink("/Users/" + "alex/notes.md", tmp_path / "docs" / "out.md")
        os.symlink("../private/config.json", tmp_path / "docs" / "conf.json")
        os.symlink("guide.md", tmp_path / "docs" / "same.md")
    except OSError:
        pytest.skip("no symbolic links here")
    (tmp_path / "docs" / "guide.md").write_text("words", encoding="utf-8")
    text = "\n".join(C.content_problems(["docs/out.md", "docs/conf.json", "docs/same.md"], set(), set()))
    assert "docs/out.md: a link whose target names a home folder" in text and "docs/out.md: a link out of the clone" in text
    assert "docs/conf.json: a link into private/" in text
    assert "docs/same.md" not in text
    # the target's name is checked for the owner's strings too, and a file in the clone it points at as before
    os.symlink("notes_by_quentin_example.md", tmp_path / "docs" / "by.md")
    (tmp_path / "docs" / "notes_by_quentin_example.md").write_text(f"at {mac()}", encoding="utf-8")
    text = "\n".join(C.content_problems(["docs/by.md"], set(), {"Quentin_Example"}))
    assert "docs/by.md: a link whose target names the owner's name" in text and "docs/by.md: holds a MAC address" in text


def test_only_the_documented_places_in_private_are_named(tmp_path, monkeypatch):
    """A public file may name private/ itself and its four documented places, never another folder of it (the
    maintainers' own notes, an archive, a person's folder): refused with the file, the line and the path, in a
    comment too. The paths refused are put together here, so this file names none of them."""
    monkeypatch.setattr(C, "ROOT", tmp_path)
    log, old = "private/" + "docs/LOG.md", "private/" + "archive/first_kit"
    (tmp_path / "a.md").write_text("Your settings go in `private/config.json`, the camera's help in private/help/.\n"
                                   f"What each session did is in {log}.\n", encoding="utf-8")
    (tmp_path / "b.py").write_text(f"x = 1\n# the first kit: {old}\n", encoding="utf-8")
    (tmp_path / "c.md").write_text("Keep your own `private/` in a repository of your own.\n", encoding="utf-8")
    found = C.content_problems(["a.md", "b.py", "c.md"], set(), set())
    tail = "; the maintainer's own folders stay out of the public files; the documented locations are "
    assert found == [f"a.md:2: names {log}{tail}{C.PRIVATE_OK_WORDS}", f"b.py:2: names {old}{tail}{C.PRIVATE_OK_WORDS}"]


@pytest.mark.parametrize("text,named", [
    ("private/" + "docs/LOG.md", "private/" + "docs/LOG.md"),
    ("see ../private/" + "alex/notes.txt", "private/" + "alex/notes.txt"),          # a person's folder, relative
    ("(private/" + "archive)", "private/" + "archive"), ("in private/" + "notes.", "private/" + "notes"),
    ("private/" + "donn\u00e9es.json", "private/" + "donn\u00e9es.json"),
    # the first name is the whole name: a documented one's prefix is not enough
    ("private/" + "datasets/", "private/" + "datasets/"), ("private/" + "help_notes.md", "private/" + "help_notes.md"),
    # from the clone's root, however it is written: only macOS's own folders are exempt (below)
    ("/private/" + "docs/LOG.md", "private/" + "docs/LOG.md"),
    ('"$ROOT"/private/' + "docs/LOG.md", "private/" + "docs/LOG.md"),
    ("${ROOT}/private/" + "archive", "private/" + "archive"),
    ("$(git rev-parse --show-toplevel)/private/" + "docs/LOG.md", "private/" + "docs/LOG.md"),
    ("<clone>/private/" + "docs/LOG.md", "private/" + "docs/LOG.md"),
    ("camset/private/" + "tmp/x", "private/" + "tmp/x"),                             # the clone's, not macOS's
    # with backslashes, as Windows writes a path and as a string in code doubles them
    ("camset\\private\\" + "docs\\LOG.md", "private\\" + "docs\\LOG.md"),
    ("C:\\\\camset\\\\private\\\\" + "archive\\\\first_kit", "private\\\\" + "archive\\\\first_kit"),
    ("in private\\" + "help_notes.md.", "private\\" + "help_notes.md"),            # a file name: a path too
    ("private/", None), ("your `private/`.", None), ("private/config.json.", None), ("private/help/help_x.json", None),
    ("../private/camsets", None), ("private/data/picture_profile/properties.json", None), ("private/help.", None),
    ("private\\config.json", None), ("private\\help\\help_x.json", None),
    ('print("kept in private\\n")', None),                                           # a string's escape, not a folder
    ("kept in private\\" + "nThe end", None), ("private\\" + "tab and more", None),  # an escape before a word
    ("/private/tmp/claude/x", None), (" /private/var/folders/x", None),               # macOS's own, not the clone's
    ("`/private/etc/hosts`", None), ("my_private/notes", None),
    # a placeholder after private/ names no folder, whichever way it is written
    ("private/<name>/", None), ("private/{name}/notes.md", None), ("private/%s", None), ("private/$NAME/x", None),
    ("private/*.json", None),
])
def test_a_path_under_private_is_one_of_the_documented_places(text, named):
    found = C.private_path_problems("f.md", text)
    assert [x.split(";")[0] for x in found] == ([f"f.md:1: names {named}"] if named else [])


def test_a_published_images_metadata_names_no_body_or_person(tmp_path, monkeypatch):
    """A photo's EXIF holds the body's serial and the owner with no label the text patterns know: refused in a
    published image; a screenshot's plain EXIF (its size and colour space) passes."""
    from PIL import ExifTags, Image
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "docs" / "images").mkdir(parents=True)
    exif = Image.Exif()
    exif[ExifTags.IFD.Exif] = {0xA431: "4419" + "233", 0xA002: 8}
    exif[0x013B] = "Quentin Example"
    Image.new("RGB", (8, 6)).save(tmp_path / "docs" / "images" / "photo.jpg", "JPEG", exif=exif)
    plain = Image.Exif()
    plain[ExifTags.IFD.Exif] = {0xA001: 1, 0xA002: 8, 0xA003: 6}
    plain[0x8298] = " "                                              # a blank copyright names nobody
    plain[ExifTags.IFD.GPSInfo] = {0: b"\x02\x02\x00\x00"}           # a GPS version alone is no position
    Image.new("RGB", (8, 6)).save(tmp_path / "docs" / "images" / "shot.png", "PNG", exif=plain)
    # a PNG's text chunk and XMP name a person too, where no EXIF does
    from PIL import PngImagePlugin
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Author", "Quentin Example")
    meta.add_itxt("XML:com.adobe.xmp", '<x:xmpmeta><dc:rights><rdf:Alt><rdf:li xml:lang="x-default">Quentin Example'
                  '</rdf:li></rdf:Alt></dc:rights></x:xmpmeta>')
    Image.new("RGB", (8, 6)).save(tmp_path / "docs" / "images" / "text.png", "PNG", pnginfo=meta)
    found = C.content_problems(["docs/images/photo.jpg", "docs/images/shot.png", "docs/images/text.png"], set(), set())
    tail = "; strip it before publishing (for example: open it and save a copy without metadata)"
    assert found == ["docs/images/photo.jpg: its metadata (EXIF, PNG text or XMP) holds the body's serial number, an "
                     "artist's name" + tail,
                     "docs/images/text.png: its metadata (EXIF, PNG text or XMP) holds an author's name, a copyright "
                     "holder" + tail]


def test_a_long_run_of_address_letters_takes_no_time():
    """The e-mail pattern is tried from the start of a run of its characters only: from every character, a run of
    300,000 with no @ took over a minute (HEAD the same); a minified file or a binary's string could stall the hook."""
    import time
    t0 = time.monotonic()
    assert C.leaks("1." * 150000) == [] and C.leaks("xy-" * 100000) == []
    assert time.monotonic() - t0 < 5


# ---------------------------------------------------------------- nothing HEAD refused is let through

# the guard as it was before the review of 2026-11-07 (git show BASELINE:kit/tools/check_public.py): the new one must
# refuse everything it refused, but the placeholders the new one documents
BASELINE = "97b8297"
P = (0x5C, 0x12, 0x34, 0x56, 0x78, 0x9A)


def corpus() -> list:
    """Strings the guards are asked about: every case of this file's tests and of reviews 1 and 2, refused and allowed,
    each on its own and in a sentence."""
    real6 = v6(0xfe80, 0, 0, 0, 0x1c2d, 0x3e4f, 0x5061, 0x7a8b)
    cisco = "{}{}.{}{}.{}{}".format(*(f"{x:02x}" for x in P))
    out = [mac(), mac("-").upper(), cisco, mac(pairs=(0x58, 0x18, 0x62, 1, 2, 3)),
           "00:11:22:33:44:55", "0a-1b-2c-3d-4e-5f", "AA:BB:CC:DD:EE:FF", ":".join(["ab"] * 10), "SHA256:" + mac() + ":de",
           "mac:" + mac(), "MAC:" + mac().upper(), "bssid:" + mac(), "uid:" + mac(), "ILCE-1M2-" + mac("-").upper(),
           "camera-" + mac("-"), mac() + "-dev", "mac" + ": " + mac(""), "hmac: " + mac(""), "00-00-5E-00-53-01",
           "mac:" + cisco, ip(10, 1, 2, 3), ip(172, 20, 0, 9), ip(192, 168, 7, 44), ip(169, 254, 3, 3),
           ip(100, 64, 3, 9), ip(192, 168, 1, 50), ip(127, 0, 0, 1), ip(192, 0, 2, 10), ip(203, 0, 113, 7),
           ip(192, 168, 1, 5).replace(".1.", ".001."), "version 1.2.3.4", "00:00:12", "::ffff:" + ip(192, 168, 7, 5),
           "::ffff:" + ip(192, 0, 2, 1), real6, "addr:" + real6, real6 + ":", "fc00::/7", "fd00::1",
           v6(0xfd12, 0x3456, 0x789a, 0, 0, 0, 0, 1), "Serial" + "Number = 4419" + "233", '"serial"' + ': "AB55' + '01234"',
           "serial: 1234567", "serial_no" + ": 4419" + "233", "S/N" + ": 4419" + "233", "SN" + "=4419" + "233",
           "Serial #" + "4419" + "233", "isn" + ": 4419" + "233", "alex" + "@" + "mail.test",
           "alex+cam" + "@" + "mail.isp.test", "noreply" + "@anthropic.com", "alex" + "@" + "mail.example.com",
           "no-reply" + "@github.com", "alex" + "@" + "example.com", "/Users/" + "alex/camset", "/home/" + "alex/runs",
           "/Users/first/camset", "C:\\Users\\First\\camset", "C:\\Users\\" + "alex", "C:\\\\Users\\\\" + "alex",
           "xC:\\Users\\" + "alex", "C:/Users/" + "alex", "C:/home/" + "alex", "c:\\users\\" + "alex",
           "/mnt/c/Users/" + "alex", "file:/Users/" + "alex", "https://api.github.com/users/alex"]
    return [f"see {t} here" for t in out] + out


CODES = {"a MAC address": "M", "a private network address": "P", "a serial number": "S", "an e-mail address": "E",
         "a home folder": "H"}


def kinds(guard, text) -> set:
    """The kinds a guard finds in a text, by their letter in CODES (another kind by its own name)."""
    return {CODES.get(k, k) for k, _ in guard.leaks(text)}


# what the new guard lets through although the baseline refused it: the placeholders it documents (RFC 2606's
# example domains below example.com/.org/.net, a no-reply address, RFC 7042's documentation MACs)
DOCUMENTED = {"alex" + "@" + "mail.example.com", "no-reply" + "@github.com", "00-00-5E-00-53-01"}
# the baseline's kinds on each corpus string, in the corpus' order ("-" none), kept for a clone without its commit (a
# shallow CI checkout); test_nothing_the_baseline_guard_refused_passes_now checks it against the baseline itself
BASELINE_KINDS = (                       # in a sentence, then on its own: the same verdicts twice
    "M M M M - - - M M M M M M M M M - - M M P P P P P - - - - - - - P - - - "
    "- - - - S S - S - - - - E E - E E - H H - - H H H H H - H H - "
    "M M M M - - - M M M M M M M M M - - M M P P P P P - - - - - - - P - - - "
    "- - - - S S - S - - - - E E - E E - H H - - H H H H H - H H - ").strip()


def baseline_guard(tmp_path, monkeypatch):
    """The baseline guard, from git, imported with stand-ins for what it imports from today's kit (leaks() needs
    only re and ipaddress), so a rename in camkit or make_sample never fails this for a reason not the guard's; None
    where git or the commit is not here."""
    if shutil.which("git") is None:
        return None
    r = subprocess.run(["git", "show", f"{BASELINE}:kit/tools/check_public.py"], cwd=C.ROOT, capture_output=True)
    if r.returncode:
        return None
    import importlib.util
    import types
    (tmp_path / "check_public_baseline.py").write_bytes(r.stdout)
    kit = types.ModuleType("camkit")
    kit.ROOT, kit.camset, kit.definitions, kit.help_files, kit.paths = C.ROOT, None, None, None, None
    sample = types.ModuleType("make_sample")
    sample.A1II_MODEL, sample.DEFAULT_PREFIX, sample.PREFIX, sample.personal = "", b"", 0, None
    with monkeypatch.context() as m:
        m.setattr(sys, "path", list(sys.path))          # its sys.path.insert stays in here
        m.setitem(sys.modules, "camkit", kit)
        m.setitem(sys.modules, "make_sample", sample)
        spec = importlib.util.spec_from_file_location("check_public_baseline", tmp_path / "check_public_baseline.py")
        old = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(old)
    return old


def frozen() -> list:
    return [set() if k == "-" else set(k) for k in BASELINE_KINDS.split()]


def test_nothing_the_baseline_guard_refused_passes_now(tmp_path, monkeypatch):
    """The new guard refuses a superset of what the guard before the review refused, but the documented placeholders:
    the baseline is taken from git and imported beside the new one, and every string of the corpus is asked of both
    (a kind the baseline found is found again). Where git or the baseline commit is not here (a shallow CI checkout)
    this skips; BASELINE_KINDS keeps the verdicts it gave, for the test after this one."""
    old = baseline_guard(tmp_path, monkeypatch)
    if old is None:
        pytest.skip(f"the baseline guard ({BASELINE}) is not in this clone")
    lost = [(t, kinds(old, t) - kinds(C, t)) for t in corpus()
            if kinds(old, t) - kinds(C, t) and not any(d in t for d in DOCUMENTED)]
    assert lost == []
    got = " ".join("".join(sorted(kinds(old, t))) or "-" for t in corpus())
    assert got == BASELINE_KINDS, f"BASELINE_KINDS is out of date; the baseline gives: {got}"


def test_the_baseline_refusals_are_still_refused():
    """Wherever the baseline commit is or is not: each kind it found in a corpus string is found now, but in the
    documented placeholders."""
    texts = corpus()
    assert len(frozen()) == len(texts), "BASELINE_KINDS is out of step with corpus()"
    assert [(t, k - kinds(C, t)) for t, k in zip(texts, frozen(), strict=True)
            if k - kinds(C, t) and not any(d in t for d in DOCUMENTED)] == []


def test_the_repository_passes():
    assert C.problems(everything=True) == []


def test_udev_rule_is_for_the_user_at_the_seat():
    import setup as S
    assert 'TAG+="uaccess"' in S.UDEV_LINE and "0666" not in S.UDEV_LINE


def test_a_home_address_kept_as_raw_bytes_is_refused(tmp_path, monkeypatch):
    """A home address packed as a settings file may keep one (four bytes, in either order) or written out inside a
    binary file is refused like one in a text; the docs' placeholders stay allowed."""
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "private").mkdir()
    home = ip(10, 0, 7, 21)
    (tmp_path / "private" / "config.json").write_text(json.dumps({"camera_ip": home}), encoding="utf-8")
    addresses, _ = C.private_tokens()
    packed = bytes([10, 0, 7, 21])
    monkeypatch.setattr(C, "samples", lambda: {"a.DAT": {}, "b.DAT": {}, "c.DAT": {}, "d.DAT": {}})
    (tmp_path / "a.DAT").write_bytes(b"\0\1" + packed + b"\0")
    (tmp_path / "b.DAT").write_bytes(b"\0\1" + packed[::-1] + b"\0")
    (tmp_path / "c.DAT").write_bytes(b"\0\1" + home.encode("ascii") + b"\0")
    (tmp_path / "d.DAT").write_bytes(b"\0\1" + bytes([192, 168, 1, 100]) + b"\0")          # a docs' placeholder
    found = C.content_problems(["a.DAT", "b.DAT", "c.DAT", "d.DAT"], addresses, set())
    assert sorted(x.split(":")[0] for x in found if "home network address" in x) == ["a.DAT", "b.DAT", "c.DAT"]
    assert not [x for x in found if x.startswith("d.DAT")]


def test_every_commit_of_a_pull_request_is_checked_for_what_is_private(tmp_path):
    """Review 4 (2026-11-11): a pull request publishes its branch's whole history, so check_public --commits BASE..HEAD
    reads every commit's changed files from git's objects: a menu tree added in data/ and deleted by a later commit, a
    definition with evidence later made lean, a reset file not lean, a file under private/: each refused by its commit,
    though the last tree is clean; a range of clean commits passes."""
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    cam = "ILCE-0X0_fw1.00"
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    base = git("rev-parse", "HEAD")
    data = tmp_path / "data" / cam
    data.mkdir(parents=True)
    (data / f"menu_tree_{cam}.json").write_text("{}", encoding="utf-8")
    (data / f"settings_reset_{cam}.json").write_text(json.dumps({"test": "t", "records": {}}), encoding="utf-8")
    defs = tmp_path / "editor" / "definitions"
    defs.mkdir(parents=True)
    (defs / f"{cam}.json").write_text(json.dumps({"settings": [{"key": "global:0x0001", "source": "Menu"}]}),
                                      encoding="utf-8")
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "notes.txt").write_text("mine\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "my camera")
    (data / f"menu_tree_{cam}.json").unlink()
    (data / f"settings_reset_{cam}.json").write_text(json.dumps({"about": "A.", "records": {}}), encoding="utf-8")
    (defs / f"{cam}.json").write_text(json.dumps({"settings": [{"key": "global:0x0001"}]}), encoding="utf-8")
    note = "/".join(("private", "notes.txt"))
    git("rm", "-q", "--cached", note)
    git("add", "-A")
    git("commit", "-q", "-m", "lean")
    found = C.commit_problems(f"{base}..HEAD", repo=tmp_path)
    first = git("rev-parse", "HEAD~1")[:12]
    assert any(x.startswith(f"{first} data/{cam}/menu_tree_{cam}.json") and "private whole" in x for x in found)
    assert any(x.startswith(f"{first} data/{cam}/settings_reset_{cam}.json") and "not lean" in x for x in found)
    assert any(x.startswith(f"{first} editor/definitions/{cam}.json") and "source" in x for x in found)
    assert any(x.startswith(f"{first} {note}") for x in found)
    assert not any(x.startswith(git("rev-parse", "HEAD")[:12]) for x in found), "the last commit is clean"
    assert "fresh branch" in found[-1]
    assert C.commit_problems("HEAD~1..HEAD", repo=tmp_path) == []
    with pytest.raises(SystemExit, match="failed"):
        C.commit_problems("nothere..HEAD", repo=tmp_path)


def _scratch_repo(tmp_path):
    def git(*a):
        return subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("config", "core.autocrlf", "false")
    (tmp_path / "README.md").write_text("x\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    return git


@pytest.mark.parametrize("name, data, why", [
    ("CAMSET01.DAT", b"CAMSET\0" + bytes(range(256)) * 4, "a settings file"),
    ("shots/frame_0001.png", b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR" + bytes(64), "a binary file outside"),
    ("notes.md", ("camera " + mac() + " in " + "/".join(("", "Users", "quentin", "camset")) + "\n").encode(),
     "a MAC address"),
    ("downloads/" + "Cr" + "SDK_v2.00.00_20250101a_Mac.zip", b"PK\x03\x04" + bytes(32), "Sony's SDK"),
], ids=["settings-file", "camera-frame", "mac-and-home", "sdk-zip"])
def test_a_commit_range_is_held_to_the_trees_rules(tmp_path, name, data, why):
    """Fix round 5 (2026-11-11): --commits held each commit to a narrow subset of the rules, so an owner's own settings
    file, a camera frame, a text file with a MAC address and a home folder, or an SDK zip outside kit/sdk/ passed when
    added in one commit and removed in the next, though --all refuses each on the tree. Now every file a commit adds or
    changes is held to the path and content rules --all runs, read from git's objects, and the finding names the commit
    that added it, not the clean one after."""
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / name).write_bytes(data)
    git("add", "-A")
    git("commit", "-q", "-m", "add")
    added = git("rev-parse", "HEAD")[:12]
    git("rm", "-q", name)
    git("commit", "-q", "-m", "remove")
    found = C.commit_problems(f"{base}..HEAD", repo=tmp_path)
    mine = [x for x in found if x.startswith(f"{added} {name}: ")]
    assert any(why in x for x in mine), found
    if name == "notes.md":
        assert any("a home folder" in x for x in mine), found
    assert not any(x.startswith(git("rev-parse", "HEAD")[:12]) for x in found), "the commit that removed it is clean"
    assert "fresh branch" in found[-1]


@pytest.mark.parametrize("where", ["kit/sdk/CameraRemote", "runs/ILCE-0X0_fw1.00", "/".join(("private", "mine"))])
def test_a_submodule_at_a_refused_path_is_refused_by_its_commit(tmp_path, where):
    """Fix round 6 (2026-11-11): --commits left submodules (gitlinks, mode 160000) out before the path rules, so one
    added under kit/sdk/, runs/ or private/ and removed in the next commit passed. A gitlink has no blob to read; its
    path is held to the path rules, and the commit that added it is named."""
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    git("update-index", "--add", "--cacheinfo", f"160000,{base},{where}")
    git("commit", "-q", "-m", "add a submodule")
    added = git("rev-parse", "HEAD")[:12]
    git("rm", "-q", "--cached", where)
    git("commit", "-q", "-m", "remove it")
    found = C.commit_problems(f"{base}..HEAD", repo=tmp_path)
    assert any(x.startswith(f"{added} {where}: ") and "never published" in x for x in found), found
    assert not any(x.startswith(git("rev-parse", "HEAD")[:12]) for x in found)


def test_a_submodule_at_an_allowed_path_passes(tmp_path):
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    git("update-index", "--add", "--cacheinfo", f"160000,{base},vendor/lib")
    git("commit", "-q", "-m", "add a submodule")
    assert C.commit_problems(f"{base}..HEAD", repo=tmp_path) == []


def test_a_version_seen_in_several_commits_is_read_and_judged_once(tmp_path, monkeypatch):
    """Fix round 6 (2026-11-11): --commits read every blob of the range at once (minutes and gigabytes for a few
    hundred commits that each change the definition). Now each blob is read in its turn through one cat-file process
    and dropped after; a version that comes back at the same path (a revert) is neither read nor judged again."""
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    note = tmp_path / "docs" / "notes.md"
    note.parent.mkdir()
    for text in ("one\n", "two\n", "one\n", "two\n", "one\n"):
        note.write_text(text, encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", text.strip())
    reads, judged = [], []
    real_read, real_judged = C._Objects.read, C.blob_judged

    def read(self, name):
        reads.append(name)
        return real_read(self, name)

    def judge(f, *a):
        judged.append(f)
        return real_judged(f, *a)
    monkeypatch.setattr(C._Objects, "read", read)
    monkeypatch.setattr(C, "blob_judged", judge)
    assert C.commit_problems(f"{base}..HEAD", repo=tmp_path) == []
    assert judged == ["docs/notes.md", "docs/notes.md"], judged
    assert len(reads) == 2, reads
    note.write_text("mail me at someone@" + "camset-owner.net\n", encoding="utf-8")
    git("commit", "-q", "-am", "leak")
    found = C.commit_problems(f"{base}..HEAD", repo=tmp_path)
    assert [x.split(" ", 1)[0] for x in found[:-1]] == [git("rev-parse", "HEAD")[:12]], found


def test_a_clean_commit_range_passes(tmp_path):
    """A range whose commits add and change only what --all lets through (a text file, a placeholder address, a
    published image without metadata) reports nothing."""
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    (tmp_path / "docs" / "images").mkdir(parents=True)
    (tmp_path / "docs" / "notes.md").write_text("Use 00:11:22:33:44:55 and " + ip(192, 168, 1, 50) + ".\n",
                                                encoding="utf-8")
    (tmp_path / "docs" / "images" / "a.bin").write_bytes(b"\0\1\2")
    git("add", "-A")
    git("commit", "-q", "-m", "one")
    (tmp_path / "README.md").write_text("y\n", encoding="utf-8")
    git("commit", "-q", "-am", "two")
    assert C.commit_problems(f"{base}..HEAD", repo=tmp_path) == []


def test_a_reset_file_not_lean_is_refused_naming_the_move(tmp_path, monkeypatch):
    """check_public refuses a public reset file in the older whole shape (the tests' words, a reading no test could
    tell), naming kit/tools/move_evidence.py, which makes it lean; a lean one with the mapper's own about passes."""
    cam = "ILCE-0X0_fw1.00"
    d = tmp_path / "data" / cam
    d.mkdir(parents=True)
    f = d / f"settings_reset_{cam}.json"
    f.write_text(json.dumps({"test": "Reset by hand", "records": {"global:0x0001": {"result": "keeps (unsure)"}}}),
                 encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", tmp_path)
    found = C.data_problems()
    assert found and all(x.startswith(f"data/{cam}/settings_reset_{cam}.json") for x in found)
    assert any(f"kit/tools/move_evidence.py --camera {cam}" in x and "not lean" in x for x in found)
    f.write_text(json.dumps({"about": "My words.", "records": {"global:0x0001": {"name": "A", "result": "keeps"}}}),
                 encoding="utf-8")
    assert C.data_problems() == []


def _staged_blob(tmp_path, git, path: str, data: bytes):
    """`data` added to the index at `path` straight from git's objects (a name the file system may not hold). Git for
    Windows refuses a name holding a control character in its index (core.protectNTFS, on there by default): there
    the test is skipped, and the guard's reading of such a name is covered by the tests that hand it git's listing
    (..._in_gits_listing_..., ..._in_the_trees_listing_...), which run on every OS."""
    f = tmp_path / ".blob"
    f.write_bytes(data)
    oid = git("hash-object", "-w", str(f))
    f.unlink()
    try:
        git("update-index", "--add", "--cacheinfo", f"100644,{oid},{path}")
    except subprocess.CalledProcessError:
        if sys.platform == "win32" and C.CONTROL_RE.search(path):
            pytest.skip("git for Windows will not put a name holding a newline in its index; the guard's reading of "
                        "such a name is tested by handing it git's listing")
        raise
    return oid


def _unlink_read_only(p: Path):
    """Deletes a file git made read-only (its objects): Windows will not delete a read-only file, so the bit is
    cleared first."""
    os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
    p.unlink()


def test_a_name_holding_a_newline_hides_no_leak_and_is_refused(tmp_path):
    """Fix round 7 (2026-11-11): definitions were read from cat-file --batch by name (<commit>:<path>), and a
    definition named editor/definitions/a<newline>b.json made two requests of one: every read after it got the
    object before, so a root file with an e-mail address in the same commit was judged as the definition and passed.
    Objects are read by id alone now, each answer checked, and a path with a control character is refused."""
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    odd = "editor/definitions/a\nb.json"
    _staged_blob(tmp_path, git, odd, b"{}")
    _staged_blob(tmp_path, git, "zz.md", ("mail me at someone@" + "camset-owner.net\n").encode())
    git("commit", "-q", "-m", "add")
    added = git("rev-parse", "HEAD")[:12]
    found = C.commit_problems(f"{base}..HEAD", repo=tmp_path)
    assert any(x.startswith(f"{added} zz.md: ") and "e-mail address" in x for x in found), found
    assert any(x.startswith(f"{added} {odd!r}: ") and "control character" in x for x in found), found


def test_a_name_holding_a_newline_in_gits_listing_hides_no_leak(tmp_path, monkeypatch):
    """The same on every OS, Windows too, where git keeps no such name in its index: the commit holds the definition
    under a plain name and git's listings (diff-tree, ls-tree) hand the guard the name with a newline, as git on
    Linux or macOS would list it. The leak beside it is still found, and the name refused."""
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    plain, odd = "editor/definitions/a_b.json", "editor/definitions/a\nb.json"
    _staged_blob(tmp_path, git, plain, b"{}")
    _staged_blob(tmp_path, git, "zz.md", ("mail me at someone@" + "camset-owner.net\n").encode())
    git("commit", "-q", "-m", "add")
    added = git("rev-parse", "HEAD")[:12]
    real_changed, real_tree = C._changed, C._tree_blobs
    monkeypatch.setattr(C, "_changed", lambda c, repo: [(odd if f == plain else f, m, b) for f, m, b in
                                                        real_changed(c, repo)])
    monkeypatch.setattr(C, "_tree_blobs", lambda c, folder, repo: [(odd if f == plain else f, b) for f, b in
                                                                    real_tree(c, folder, repo)])
    found = C.commit_problems(f"{base}..HEAD", repo=tmp_path)
    assert any(x.startswith(f"{added} zz.md: ") and "e-mail address" in x for x in found), found
    assert any(x.startswith(f"{added} {odd!r}: ") and "control character" in x for x in found), found


@pytest.mark.parametrize("name", ["docs/a\tb.md", "docs/a\rb.md", "docs/a\x1bb.md", "docs/a\x85b.md", "docs/a\x7fb.md",
                                  "docs/a\nb.md"])
def test_a_tracked_path_with_a_control_character_is_refused(name):
    found = C.path_problems([name, "docs/plain.md"], [], {})
    assert len(found) == 1 and "control character" in found[0], found


def test_a_name_with_a_control_character_is_refused_on_the_tree_too(repo):
    _staged_blob(repo, lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True,
                                                   text=True).stdout.strip(), "docs/a\nb.md", b"x\n")
    assert any("control character" in x for x in C.problems(everything=True))


def test_a_name_with_a_newline_in_the_trees_listing_is_refused(repo, monkeypatch):
    """The same on every OS, Windows too: git ls-files -z handing the guard a name with a newline (as git on Linux or
    macOS lists one) is refused, the name read whole from the NUL-separated list."""
    (repo / "docs").mkdir()
    (repo / "docs" / "plain.md").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs/plain.md"], cwd=repo, check=True)
    real = C.git
    monkeypatch.setattr(C, "git", lambda *a: real(*a) + (["docs/a\nb.md"] if a == ("ls-files", "-z") else []))
    found = C.problems(everything=True)
    assert any(x.startswith(repr("docs/a\nb.md")) and "control character" in x for x in found), found


def test_a_blob_git_does_not_hold_is_a_finding_not_a_pass(tmp_path):
    """Fix round 7: a version git does not hold (a shallow or partial clone) was judged as nothing and passed."""
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    oid = _staged_blob(tmp_path, git, "docs/notes.md", ("mail me at someone@" + "camset-owner.net\n").encode())
    git("commit", "-q", "-m", "add")
    _unlink_read_only(tmp_path / ".git" / "objects" / oid[:2] / oid[2:])
    found = C.commit_problems(f"{base}..HEAD", repo=tmp_path)
    assert any(x.startswith(f"{git('rev-parse', 'HEAD')[:12]} docs/notes.md: not readable") and "full history" in x
               for x in found), found


class _FakeGit:
    def __init__(self, answer: bytes):
        import io
        self.stdin, self.stdout = io.BytesIO(), io.BytesIO(answer)

    def wait(self):
        return 0


@pytest.mark.parametrize("answer,whose", [(b"%s blob 3\nabc\n", "other"), (b"%s blob 3\nabcX", "asked"),
                                          (b"%s blob 3\nab", "asked"), (b"%s commit\n", "asked")],
                         ids=["another-object", "no-newline-after", "cut-short", "not-a-header"])
def test_an_answer_that_is_not_the_object_asked_for_fails_closed(tmp_path, monkeypatch, answer, whose):
    """Fix round 7: the reader takes an answer only when its header names the id asked for and a newline follows the
    object; anything else stops the reading with a finding, never a pass."""
    git = _scratch_repo(tmp_path)
    base = git("rev-parse", "HEAD")
    oid = _staged_blob(tmp_path, git, "docs/notes.md", b"abc")
    git("commit", "-q", "-m", "add")
    told = answer % ("0" * 40 if whose == "other" else oid).encode()
    monkeypatch.setattr(C._Objects, "__init__", lambda self, repo: setattr(self, "git", _FakeGit(told)))
    found = C.commit_problems(f"{base}..HEAD", repo=tmp_path)
    assert any("can no longer be trusted" in x for x in found), found
    reader = C._Objects.__new__(C._Objects)
    reader.git = _FakeGit(told)
    with pytest.raises(C.Unreadable):
        reader.read(oid)
    with pytest.raises(C.Unreadable, match="not an object id"):
        reader.read(f"HEAD:{'docs/notes.md'}")
