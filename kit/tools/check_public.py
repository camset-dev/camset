"""Refuse a commit that would publish what is kept private (docs/decisions/0016, 0018). Run by pre-commit and, on
every pull request, by .github/workflows/kit-ci.yml.

    .venv/bin/python kit/tools/check_public.py          # the paths of every tracked file; the contents of those staged
    .venv/bin/python kit/tools/check_public.py --all    # the contents of every tracked file too (what CI runs)
    .venv/bin/python kit/tools/check_public.py --commits BASE..HEAD   # every commit of a pull request (CI)

Paths (every tracked or staged file, as git names them byte for byte: a name with a non-ASCII letter is read as it
is, never in git's quoted form):
- Nothing under private/, runs/ or kit/sdk/ (but its README) is tracked, and no tracked file is one .gitignore
  ignores: a force-added file (git add -f) is refused.
- None of Sony's SDK files anywhere, by name: CrSDK_*, Cr*.h / ICr*.h and the other headers, libCr_* and Cr_Core,
  libmonitor_protocol*, CrAdapter/, RemoteCli*, SimpleCli*, the SDK's readme and reference (docs/RELEASING.md).
- No settings file but the definitions' samples (each named by its definition's camera section, "sample", beside it
  in editor/definitions/, personal values removed), no spreadsheet, and no binary file outside the published images
  (docs/images/, editor/assets/, kit/camkit/glyphs/) and those samples: camera frames and downloads stay in runs/ and
  private/.
- A tracked link is published as its target's name: the name is read for what follows, and a link out of the clone
  or into private/, runs/ or kit/sdk/ is refused.
- No path holds a control character (a newline, a tab, a carriage return, NUL or any other C0 or C1 one): such a name
  reads as two lines to anything that reads names a line at a time.
Contents (text files, and the ASCII strings in binary ones):
- No MAC address in any notation (aa:bb:..., aa-bb-..., aabb.ccdd.eeff, and twelve digits where a label says it is
  one: "mac": "aabbccddeeff") but the placeholders below and RFC 7042's documentation range; no private network
  address: IPv4 10/8, 172.16/12, 192.168/16, 169.254/16, 100.64/10 (leading zeros or not) but the placeholders below,
  IPv6 unique local (fc00::/7) with its network's own id (fd00::1 is the docs'), and link-local (fe80::/10, but the
  short placeholder kind such as fe80::1, and one made from a placeholder MAC), and no IPv6 address whose interface
  id is a MAC (EUI-64); no serial-number value ("serial": 1234567-like, S/N: or SN=, five digits or more); no e-mail
  address but noreply and example ones; and no home folder (/Users/NAME, /home/NAME, C:\\Users\\NAME or
  C:/Users/NAME, any case on Windows) but placeholder names.
- The published images carry no metadata that names the body or the person (EXIF: the body's serial, the owner, the
  artist, the copyright holder, a GPS position, the maker's notes; a PNG's Author, Artist, Copyright or Creator text;
  XMP's dc:creator and dc:rights).
- No path under private/ but the places the docs tell everyone to use (docs/decisions/0018): private/ itself,
  private/config.json, and what is under private/help/, private/camsets/, private/data/ and private/evidence/; any
  other, a comment's
  too, is refused with its line (the maintainers' own folders stay out of the public files). A path with backslashes
  counts when it reads as one: another backslash or slash after its first name, or a file name with an extension
  (private\\help\\help_x.json, private\\config.json), never an escape before a word (private\\nThe). Only macOS's own
  /private/tmp, /private/var and /private/etc, as absolute paths, are not the clone's; a placeholder after private/
  (<name>, {name}, %s, $NAME, *) names no folder.
- None of the home network addresses in private/config.json (but the docs' placeholders), as text or as raw bytes
  in any tracked file and the samples (written out, or packed as a settings file may keep one: an IPv4 address's four
  bytes in either order, an IPv6 address's sixteen; ~/.config/camset/network.json is never read, as it holds the
  camera's credentials, docs/decisions/0009, and no address), nor its
  "private_strings", nor the owner's name or the body's serial as the camera's properties hold them
  (private/data/picture_profile/properties.json), when present.
- Each definition's sample holds no personal value and valid checksums.
- Each definition is lean (camkit.definitions.evidence_in_public): none of the mapping's evidence (how, when, in which
  run or from which state a thing was proved), which stays in the mapper's private/evidence/ (docs/decisions/0016).
- So is every camera's data folder, data/<model>_fw<fw>/ (camkit.datafiles.evidence_in_public): no menu tree, no
  accepted file and no record shapes there (private whole), no run's folder, kit2_ run name or ISO date in any of its
  files, and a reset file as lean as kit/schema_update.py writes it (no test's own words, no reading no test could
  tell).
- Every help text in each definition (editor/definitions/<model>_fw<fw>.json) is the project's own, as its
  data/<model>_fw<fw>/help_<model>_fw<fw>.json has it, and that file says it is for the definition's own model and
  firmware (kit/camkit/help_files.py).
- No text in the definitions, data/, docs/ or kit/'s Python strings shares a run of eight words with the camera's
  In-Camera Guide text in private/help/ (when it is here), so a rewording that stayed too close to Sony's is caught.
Every commit of a range (--commits BASE..HEAD, which CI runs for a pull request: a pull request publishes its branch's
whole history, not only its last tree): each file a commit adds or changes is held to the rules above as --all holds
the tree's, the same functions on that commit's version of it: the path rules (never published, Sony's SDK, a settings
file no definition names as its sample, a spreadsheet, a file .gitignore ignores), the content rules (a binary file
by the binary rule and its ASCII strings, a text file by its text, a link by its target, a sample's personal values),
the data folder's and the definitions' leanness and the camera's In-Camera Guide text; a file added in one commit and
removed in the next is refused by the first; a submodule (gitlink) by the path rules, as it has no file to read. The
samples are the ones the range's last commit's definitions name. Each commit's files are read as blobs with git's
plumbing (diff-tree, one long-lived cat-file --batch: a blob at a time, dropped once judged, and a version seen again
at the same path judged once), nothing checked out; each finding starts with its commit. Objects are asked for by
their ids alone (from diff-tree and ls-tree -z), never by a name, and each answer must be the object asked for,
ended as git ends one; a blob git does not hold (a shallow or partial clone) or an answer that is not the one asked
for is a finding, never a file passed unread.
"""
import argparse
import ast
import fnmatch
import io
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, datafiles, definitions, help_files, paths  # noqa: E402
from make_sample import A1II_MODEL, DEFAULT_PREFIX, PREFIX, personal  # noqa: E402

RUN = 8
# MAC addresses: six pairs with one separator, a run of more refused too (a label or a name before it, such as
# "mac:" or "ILCE-1M2-", ends in a hex digit as often as not, so nothing around the pairs is taken to make them
# something else), or Cisco's three dotted quads; twelve digits with nothing between them only where a label says it
# is a MAC (not inside a word: hmac), since such runs are common elsewhere (a test's numbers, a hash)
MAC_RE = re.compile(r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}([:-])(?:[0-9A-Fa-f]{2}\1){4}[0-9A-Fa-f]{2}"
                    r"|[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4})(?![0-9A-Fa-f])")
MAC_LABELLED_RE = re.compile(r"(?<![A-Za-z])mac(?:[ _-]?addr(?:ess)?)?[\"']?\s*[:=]\s*[\"']?([0-9A-Fa-f]{12})"
                             r"(?![0-9A-Za-z])", re.I)
# the placeholders the docs and tests use (written without separators, upper case), and RFC 7042's documentation
# range, 00-00-5E-00-53-00 to -FF (mac_placeholder)
MAC_PLACEHOLDERS = {"001122334455", "0A1B2C3D4E5F", "001A2B3C4D5E", "AABBCCDDEEFF", "00AABBCCDDEE",
                    "000000000000", "FFFFFFFFFFFF", "020000000001", "000000000001"}
MAC_DOC_PREFIX = "00005E0053"
IP_RE = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
PRIVATE_NETS = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16",
                                                     "100.64.0.0/10")]
# kit/config.example.json's and the docs' made-up addresses
IP_PLACEHOLDERS = {"192.168.1.50", "192.168.1.100", "192.168.1.20", "192.168.1.60", "192.168.1.77", "192.168.1.99"}
# an IPv6 address: hex groups and colons (two colons at least), maybe a dotted IPv4 at the end, maybe a zone (%en0);
# after a label's colon ("addr:fe80::...") but not inside a name (C++'s std::string, Rust's Self::Foo) nor inside a
# longer run of groups, and before a sentence's colon or full stop; ipaddress decides what is one (ipv6s)
IP6_RE = re.compile(r"(?<![\w.])(?<![0-9A-Fa-f:]:)((?:[0-9A-Fa-f]{0,4}:){2,7}(?:[0-9A-Fa-f]{1,4}|(?:\d{1,3}\.){3}\d{1,3})?)"
                    r"(?:%[\w.-]*\w)?(?!\w)(?!\.\d)(?!:[0-9A-Fa-f])")
ULA6, LINK_LOCAL6 = ipaddress.ip_network("fc00::/7"), ipaddress.ip_network("fe80::/10")
# the documentation ranges (RFC 5737, RFC 3849): made up by definition
DOC_NETS = [ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")]
# a serial number's value after its label: serial, serial no., serial number, S/N, SN (two patterns, each starting
# from a fixed letter, which is several times faster over the whole tree than one with both)
SERIAL_VALUE = r"[\"']?\s*[:=#]\s*[\"']?([A-Za-z]{0,3}\d{5,}[A-Za-z0-9]*)"
SERIAL_RES = (re.compile(r"serial(?:[ _-]?(?:no\.?|number|num))?" + SERIAL_VALUE, re.I),
              re.compile(r"\b[Ss]/?[Nn]" + SERIAL_VALUE))
SERIAL_PLACEHOLDERS = {"1234567", "7654321", "2345678", "0000000", "12345678"}
# tried only from the start of a run of the local part's characters: from every character of it, a long run with no
# @ (a minified file, a binary's string) took minutes; a match found inside a run is found from its start too
EMAIL_RE = re.compile(r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
EMAIL_OK = re.compile(r"(?:^no-?reply@|@users\.noreply\.github\.com$|@(?:[A-Za-z0-9-]+\.)*example\.(?:com|org|net)$)",
                      re.I)
# a home folder: macOS and Linux as written, WSL's /mnt/c/users/ in any case, macOS typed in lower case (not a web
# address's /users/, which follows a host name); and Windows, in any case: with backslashes after any letter and a
# colon, as the guard always took it, with forward slashes only after a drive letter alone (C:/Users/, reported once,
# from its drive letter; not a word's colon: api:/users/list, file:/Users/ being macOS'). Its match starts at the
# colon (a pattern that starts with a letter is tried at every letter of the tree)
HOME_RE = re.compile(r"/(?:home|(?<!(?<![A-Za-z])[A-Za-z]:/)Users|(?i:mnt/[a-z]/users)|(?<![\w.:/-]/)(?i:users))"
                     r"/([A-Za-z0-9._-]+)")
HOME_WIN_RE = re.compile(r"(?<=[A-Za-z]):(?:\\{1,2}(?i:users)\\{1,2}|(?<=(?<![A-Za-z])[A-Za-z]:)/(?i:users)/)"
                         r"([A-Za-z0-9._-]+)")
HOME_OK = {"first", "you", "user", "username", "name", "me", "runner", "shared", "public", "example", "your-name",
           "yourname", "default"}
# the EXIF tags of a published image that name the body or the person (Pillow reads them; the Exif sub-directory as
# well as the first, and the GPS one when it holds a latitude or a longitude, tags 1 to 4); the PNG text keys and
# XMP's Dublin Core fields of the same kind
IMAGE_TAGS = {0xA431: "the body's serial number", 0xC62F: "the camera's serial number",
              0xA430: "the camera owner's name", 0x013B: "an artist's name", 0x8298: "a copyright holder",
              0x927C: "the camera maker's notes", 0x8825: "a GPS position"}
PNG_TEXT = {"Author": "an author's name", "Artist": "an artist's name", "Copyright": "a copyright holder",
            "Creator": "a creator's name"}
XMP_RE = re.compile(r"<dc:(creator|rights)\b(?:(?!</dc:).){0,4096}?</dc:\1>", re.S)
# Sony's SDK, by file or folder name anywhere in the tree
SDK_FILE_RE = re.compile(
    r"(^|/)(CrSDK_[^/]*|I?Cr[A-Z][A-Za-z0-9_]*\.(h|cpp)|IDeviceCallback\.h|PropertyValueTable\.h"
    r"|(lib)?Cr_[A-Za-z0-9_]*\.(so|dylib|dll|lib)[^/]*|libmonitor_protocol[^/]*|[^/]*Remote_?SDK[^/]*"
    r"|RemoteSampleApp[^/]*|(RemoteCli|SimpleCli)[^/]*)$"
    r"|(^|/)(CrAdapter|RemoteCli|SimpleCli|SourceCodeOfOpenSourceSoftware)/")
NEVER_TRACKED = ("private/", "runs/", "kit/sdk/")
# the places in private/ a public file may name (docs/decisions/0018), by the first name after private/: the kit's
# settings and the four folders the docs tell everyone to use; private/ alone names none. Any other (the maintainers'
# own notes, an archive, a person's folder) is refused
PRIVATE_OK = ("config.json", "help", "camsets", "data", "evidence")
PRIVATE_OK_WORDS = "private/, private/config.json, private/help/, private/camsets/, private/data/ and private/evidence/"
# private/ as a path: not the end of a longer name (my_private/, .private/); then its separator (/, or one or two
# backslashes, as Windows and a string in code write it), its first name read up to a character no name holds (a
# quote, a space, a bracket, a placeholder's <, {, %, $ or *), and the rest of the path, which the finding shows. After
# a backslash, only a path-like name counts (BACKSLASH_FILE_RE below): an escape before a word (private\nThe) is not a
# folder
PRIVATE_PATH_RE = re.compile(r"(?<![\w.-])private(/|\\{1,2})([\w.@+~=-]*)((?:(?:/|\\{1,2})[\w.@+~=-]*)*)")
# macOS's own folders under its /private/, the only private/ paths not the clone's: as absolute paths alone (the slash
# before private/ follows no name), so a path from the clone's root (/private/<name>, "$ROOT"/private/<name>) is the
# clone's unless it is one of these
MACOS_PRIVATE = ("tmp", "var", "etc")
# a first name after a backslash that reads as a path: another separator follows it, or it is a file name with an
# extension
BACKSLASH_FILE_RE = re.compile(r"\.[A-Za-z0-9]{1,8}$")
# binary files that may be published: the docs' images, the editor's icon, the screen reader's glyphs (and the
# definitions' samples, samples() below)
BINARY_OK = ["docs/images/*", "editor/assets/*", "kit/camkit/glyphs/*"]


_DEFINITIONS = {}


def definition_files() -> list:
    """[(path, definition)] of every definition in editor/definitions/ (read once)."""
    if ROOT not in _DEFINITIONS:
        found = []
        for p in sorted((ROOT / "editor" / "definitions").glob("*.json")):
            try:
                found.append((p, json.loads(p.read_text(encoding="utf-8"))))
            except ValueError:
                continue
        _DEFINITIONS[ROOT] = found
    return _DEFINITIONS[ROOT]


def samples() -> dict:
    """{the published path of a definition's sample: its definition} for every definition that names one."""
    out = {}
    for p, doc in definition_files():
        s = definitions.sample(doc, p)
        if s is not None:
            out[s.relative_to(ROOT).as_posix()] = doc
    return out


def sony_sdk(path: str) -> bool:
    """A tracked path that is Sony's SDK: anything in kit/sdk/ but its README, or one of the SDK's own files anywhere."""
    return (path.startswith("kit/sdk/") and path != "kit/sdk/README.md") or bool(SDK_FILE_RE.search(path))


def words(text: str) -> list:
    return re.findall(r"[a-z0-9]+", text.lower())


def runs(text: str) -> set:
    w = words(text)
    return {tuple(w[i:i + RUN]) for i in range(max(1, len(w) - RUN + 1))}


def texts(table: dict):
    for key, t in table.items():
        if t.get("help"):
            yield key, t["help"]
        for v, h in t.get("option_help") or []:
            yield f"{key} = {v}", h


def git(*args) -> list:
    """The paths a git command lists, one per NUL (its -z): each as it is, a non-ASCII name too, never in git's
    quoted form, which no path test would match. Stops when git does not answer: an empty list would pass the guard."""
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True)
    except OSError as e:
        raise SystemExit(f"check_public: git is needed to list the tracked files ({e})") from None
    if r.returncode:
        raise SystemExit(f"check_public: git {' '.join(args)} failed: {r.stderr.decode('utf-8', 'replace').strip()}")
    return [p for p in r.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


def ascii_strings(data: bytes, least: int = 6) -> str:
    """The printable ASCII runs of a binary file, one per line (as `strings` gives them)."""
    return "\n".join(m.decode("ascii") for m in re.findall(rb"[\x20-\x7e]{%d,}" % least, data))


def ipv4(text: str):
    """The IPv4 address a dotted quad is, leading zeros or not (192.168.001.005 too, which ipaddress refuses as
    written); None when an octet is past 255."""
    parts = [int(x) for x in text.split(".")]
    return ipaddress.IPv4Address(".".join(map(str, parts))) if all(x <= 255 for x in parts) else None


def ipv6s(text: str):
    """(as written, the address) of every IPv6 address in the text; a sentence's colon after one is not part of it."""
    for m in IP6_RE.finditer(text):
        written, addr = m.group(0), m.group(1)
        if addr.endswith(":") and not addr.endswith("::"):
            written, addr = written.replace(addr, addr[:-1], 1), addr[:-1]
        try:
            yield written, ipaddress.IPv6Address(addr)
        except ValueError:
            continue


def mac_placeholder(digits: str) -> bool:
    """Twelve hex digits (any case) one of the made-up MACs the docs use, or in RFC 7042's documentation range."""
    d = digits.upper()
    return d in MAC_PLACEHOLDERS or d.startswith(MAC_DOC_PREFIX)


def eui64_mac(ip) -> str | None:
    """The MAC an IPv6 address's interface id was made from (EUI-64: ff:fe in its middle, the universal bit flipped),
    as twelve upper-case digits; None when it was not made from one."""
    iid = int(ip) & (2 ** 64 - 1)
    if (iid >> 24) & 0xFFFF != 0xFFFE:
        return None
    mac = ((iid >> 40) << 24 | (iid & 0xFFFFFF)) ^ (0x02 << 40)
    return f"{mac:012X}"


def private6(ip) -> bool:
    """An IPv6 address of the owner's own network: unique local with its network's random 40-bit id (fd12:3456:789a::;
    fc00::/7 itself and fd00::1 are the zero id the docs use), or link-local with an interface id past the short
    placeholder kind (fe80::1) and not made from a placeholder MAC."""
    if ip in ULA6:
        return (int(ip) >> 80) & (2 ** 40 - 1) != 0
    mac = eui64_mac(ip)          # a link-local's interface id is all it says: one made from a placeholder MAC, nothing
    return ip in LINK_LOCAL6 and int(ip) & (2 ** 64 - 1) > 0xFFFF and not (mac and mac_placeholder(mac))


def addresses(text: str) -> set:
    """Every IPv4 and IPv6 address in the text, each in its one written form (str of ipaddress)."""
    out = {str(ip) for ip in map(ipv4, IP_RE.findall(text)) if ip is not None}
    return out | {str(ip.ipv4_mapped or ip) for _, ip in ipv6s(text)}


def leaks(text: str) -> list:
    """What in the text looks like the owner's network, body or person: (kind, the match)."""
    out = []
    for m in MAC_RE.finditer(text):
        if not mac_placeholder(re.sub(r"[^0-9A-Fa-f]", "", m.group(0))):
            out.append(("a MAC address", m.group(0)))
    for m in MAC_LABELLED_RE.finditer(text):
        if not mac_placeholder(m.group(1)):
            out.append(("a MAC address", m.group(1)))
    for m in IP_RE.finditer(text):
        ip = ipv4(m.group(0))
        if ip is not None and any(ip in n for n in PRIVATE_NETS) and str(ip) not in IP_PLACEHOLDERS:
            out.append(("a private network address", m.group(0)))
    for written, ip in ipv6s(text):
        mac = eui64_mac(ip)
        if mac and not mac_placeholder(mac):
            out.append(("a MAC address (an IPv6 address made from it)", written))
        elif not ip.ipv4_mapped and private6(ip):
            out.append(("a private network address", written))
    for rx in SERIAL_RES:
        out += [("a serial number", m.group(1)) for m in rx.finditer(text) if m.group(1) not in SERIAL_PLACEHOLDERS]
    for m in EMAIL_RE.finditer(text):
        if not EMAIL_OK.search(m.group(0)):
            out.append(("an e-mail address", m.group(0)))
    for rx, back in ((HOME_RE, 0), (HOME_WIN_RE, 1)):          # Windows': shown from its drive letter
        out += [("a home folder", text[m.start() - back:m.end()]) for m in rx.finditer(text)
                if m.group(1).lower() not in HOME_OK]
    return out


def never_published(path: str) -> bool:
    """A path under private/, runs/ or kit/sdk/ (but the SDK folder's README)."""
    return path.startswith(NEVER_TRACKED) and path != "kit/sdk/README.md"


def macos_own(text: str, at: int, sep: str, first: str) -> bool:
    """private/ at `at` is macOS's /private/tmp, /private/var or /private/etc, an absolute path: its slash follows no
    name (the start, a space, a quote, a bracket), as in /private/tmp/x; after a folder's name it is the clone's."""
    before = text[at - 2:at] if at >= 2 else text[:at]
    return (sep == "/" and first in MACOS_PRIVATE and before.endswith("/")
            and not (len(before) == 2 and (before[0].isalnum() or before[0] in "_.")))


def private_path_problems(f: str, text: str) -> list:
    """Each path under private/ a public file names that is not one of the documented places (PRIVATE_OK) nor macOS's
    own (macos_own), with its line; a sentence's full stop after a name is not part of it. After a backslash only a
    path counts (another separator after the first name, or a file name with an extension), not a string's escape
    before a word (private\\nThe, private\\tab)."""
    out = []
    for m in PRIVATE_PATH_RE.finditer(text) if "private/" in text or "private\\" in text else ():
        sep, name, rest = m.groups()
        first = name if rest else name.rstrip(".")
        if (not first or first in PRIVATE_OK or macos_own(text, m.start(), sep, first)
                or (sep != "/" and not rest and not BACKSLASH_FILE_RE.search(first))):
            continue
        line = text.count("\n", 0, m.start()) + 1
        named = ("private" + sep + name + rest).rstrip(".")
        out.append(f"{f}:{line}: names {named}; the maintainer's own folders stay out of the public files; the "
                   f"documented locations are {PRIVATE_OK_WORDS}")
    return out


CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")          # C0, DEL and C1, as code points


def path_problems(paths: list, ignored: list, published: dict = None) -> list:
    """The path rules (Paths, above) over `paths`; `ignored` the ones .gitignore ignores; `published` the definitions'
    samples (samples(), by default the tree's)."""
    out, published = [], samples() if published is None else published
    for f in paths:
        if CONTROL_RE.search(f):
            out.append(f"{f!r}: the name holds a control character (a newline, a tab, NUL or another); rename it: a "
                       "name that reads as two lines is never published")
        if never_published(f):
            out.append(f"{f}: {f.split('/')[0]}/ is never published (private/, runs/ and Sony's SDK stay on your "
                       "computer); git rm --cached it")
        elif sony_sdk(f):
            out.append(f"{f}: Sony's SDK is never published (its agreement: docs/RELEASING.md); only kit/sdk/README.md "
                       "is tracked")
        if f.lower().endswith(".dat") and f not in published:
            out.append(f"{f}: a settings file, and no definition names it as its sample; real ones belong in "
                       "private/camsets (kit/tools/make_sample.py makes a public one beside its definition)")
        if f.lower().endswith((".xlsx", ".xls", ".numbers")):
            out.append(f"{f}: a spreadsheet (those held real files' values); keep it in private/")
    out += [f"{f}: .gitignore ignores it, yet it is tracked (force-added): git rm --cached it" for f in ignored]
    return out


def home_address(ip) -> bool:
    """An address of the owner's network as private/config.json names one: a unicast host, not loopback, not a
    netmask or 0.0.0.0, not a documentation range nor one of the docs' placeholders (an owner who kept the example's
    reader address must still be able to commit the docs that name it)."""
    return not (ip.is_loopback or ip.is_unspecified or ip.is_multicast or ip.is_reserved
                or any(ip.version == n.version and ip in n for n in DOC_NETS) or str(ip) in IP_PLACEHOLDERS)


def private_tokens() -> tuple:
    """(home addresses, owner strings) from private/ when it is here."""
    conf = ROOT / "private" / "config.json"
    dump = ROOT / "private" / "data" / "picture_profile" / "properties.json"
    props = [x for x in json.loads(dump.read_text(encoding="utf-8")) if len(x.get("text") or "") >= 4] if dump.exists() else []
    owner = {x["text"] for x in props if x.get("name") in ("SetPhotographer", "SetCopyright", "BodySerialNumber")}
    home = set()
    if conf.exists():
        text = conf.read_text(encoding="utf-8")
        try:
            cfg = json.loads(text)
        except ValueError as e:
            raise SystemExit(f"check_public: private/config.json is not valid JSON ({e}): its addresses and "
                             "private_strings cannot be checked") from None
        home = {a for a in addresses(text) if home_address(ipaddress.ip_address(a))}
        owner |= {s for s in cfg.get("private_strings") or [] if isinstance(s, str) and len(s) >= 4}
    return home, owner


def raw_forms(home: set) -> list:
    """The byte strings each home address can be kept as: written out (ASCII), and packed, an IPv4 address's four
    bytes in network order and reversed (a little-endian number), an IPv6 address's sixteen."""
    out = []
    for a in sorted(home):
        ip = ipaddress.ip_address(a)
        out += [a.encode("ascii"), ip.packed] + ([ip.packed[::-1]] if ip.version == 4 else [])
    return out


def raw_home(data: bytes, home: set) -> bool:
    """Whether the bytes hold a home address in any of its raw forms (raw_forms)."""
    return any(b in data for b in raw_forms(home))


def owner_problems(f: str, text: str, home: set, owner: set, holds: str = "holds") -> list:
    """private/'s own: a home network address from private/config.json, the owner's name or serial."""
    out = [f"{f}: {holds} a home network address from private/config.json"] if home and home & addresses(text) else []
    low = text.lower()
    return out + [f"{f}: {holds} the owner's name or serial from the camera's properties or private_strings"
                  for n in owner if n.lower() in low]


def link_problems(f: str, target: str, home: set = frozenset(), owner: set = frozenset(), root: Path = None) -> list:
    """A tracked link: git publishes its target's name; the file it points at is checked as a file of its own when it
    is one in the clone (content_problems), as before links were told apart. `root`: the clone it is read in."""
    root = ROOT if root is None else root
    holds = "a link whose target names"
    out = [f"{f}: {holds} {kind} ({what})" for kind, what in leaks(target)] + owner_problems(f, target, home, owner, holds)
    where = os.path.normpath((root / f).parent / target)
    try:
        rel = Path(where).relative_to(root).as_posix()
    except ValueError:
        return out + [f"{f}: a link out of the clone ({target}); publish the file itself, or nothing"]
    if never_published(rel):
        out.append(f"{f}: a link into {rel.split('/')[0]}/ ({target}), which is never published")
    return out


def image_problems(f: str, data: bytes) -> list:
    """The EXIF of a published image (its bytes) that names the body or the person (IMAGE_TAGS); none from a file
    Pillow does not read as an image, or without Pillow."""
    try:
        from PIL import Image
    except ImportError:
        return []
    try:
        with Image.open(io.BytesIO(data)) as im:
            exif = im.getexif()
            gps = exif.get_ifd(0x8825)
            tags = {**exif, **exif.get_ifd(0x8769)}
            tags[0x8825] = 1 if any(t in gps for t in (1, 2, 3, 4)) else None          # a position, not a version alone
            info = dict(im.info)
    except Exception:                                     # noqa: BLE001  not an image Pillow reads: nothing to say
        return []

    def held(v) -> bool:
        return v not in (None, b"") and (not isinstance(v, str) or v.strip() != "")
    found = [why for tag, why in IMAGE_TAGS.items() if held(tags.get(tag))]
    found += [why for key, why in PNG_TEXT.items() if held(info.get(key)) and why not in found]
    xmp = info.get("XML:com.adobe.xmp") or info.get("xmp") or ""
    xmp = xmp.decode("utf-8", "replace") if isinstance(xmp, bytes) else str(xmp)
    for m in XMP_RE.finditer(xmp):
        why = "a creator's name" if m.group(1) == "creator" else "a copyright holder"
        if re.sub(r"<[^>]*>", "", m.group(0)).strip() and why not in found:
            found.append(why)
    return [f"{f}: its metadata (EXIF, PNG text or XMP) holds {', '.join(found)}; strip it before publishing (for "
            "example: open it and save a copy without metadata)"] if found else []


def content_problems(files: list, home: set, owner: set) -> list:
    """The content rules (Contents, above) over the tree's files: each read from the clone (a link's target as git
    publishes it, and the file it points at read through, as git's checkout leaves it readable)."""
    out, published = [], samples()
    for f in files:
        p = ROOT / f
        if p.is_symlink():
            out += link_problems(f, os.readlink(p), home, owner)
        if p.is_file():
            out += file_problems(f, p.read_bytes(), home, owner, published)
    return out


def file_problems(f: str, data: bytes, home: set, owner: set, published: dict) -> list:
    """The content rules over one file, `f` its path and `data` its bytes (from the tree, or a commit's blob): a binary
    file by the binary rule (the published images' metadata, the definitions' samples) and its ASCII strings, a text
    file by its text; `published` the definitions' samples."""
    out = []
    try:
        text, binary = data.decode("utf-8"), b"\0" in data
    except UnicodeDecodeError:
        text, binary = None, True
    if binary:
        if any(fnmatch.fnmatch(f, g) for g in BINARY_OK):
            out += image_problems(f, data)
        elif f not in published:
            out.append(f"{f}: a binary file outside the published images ({', '.join(BINARY_OK)}) and the "
                       "definitions' samples: camera frames and downloads stay in runs/ and private/")
        text = ascii_strings(data)
    own = owner_problems(f, text, home, owner)
    out += own
    if home and not any("home network address" in x for x in own) and raw_home(data, home):
        out.append(f"{f}: holds a home network address from private/config.json as raw bytes (written out in a "
                   "binary string, or packed)")
    if not binary:
        out += private_path_problems(f, text)
    if f == "kit/tools/check_public.py":
        return out                                        # this file's own placeholders and patterns
    seen = set()
    for kind, what in leaks(text):
        if (kind, what) not in seen:
            seen.add((kind, what))
            out.append(f"{f}: holds {kind} ({what}); use a placeholder (see kit/tools/check_public.py)")
    return out


def sample_problems(home: set, owner: set) -> list:
    out = []
    for rel, doc in samples().items():
        sample = ROOT / rel
        if not sample.exists():
            out.append(f"{rel}: the definition names it as its sample, and it is not there")
            continue
        out += one_sample(rel, sample.read_bytes(), doc, home, owner)
    return out


def one_sample(rel: str, raw_sample: bytes, doc: dict, home: set, owner: set) -> list:
    """A definition's sample (`rel`, its bytes): no personal value, no home address or owner string, valid checksums,
    the definition's model."""
    out = []
    if home and raw_home(raw_sample, home):
        out.append(f"{rel}: holds a home network address from private/config.json (written out or packed)")
    for n in owner:
        if n.lower().encode("utf-8") in raw_sample.lower():
            out.append(f"{rel}: holds the owner's name or serial from the camera's properties")
    try:
        cs = camset.parse(raw_sample, check=False, name="the sample")
    except ValueError as e:
        return out + [f"{rel}: {e}"]
    if not cs.checksums_ok:
        out.append(f"{rel}: invalid checksums")
    if cs.model != doc["model"]:
        out.append(f"{rel}: a {cs.model} file, the sample of the {doc['model']}'s definition")
    pref = cs.get(0, PREFIX) if cs.model == A1II_MODEL else None          # the a1 II's record id (make_sample.py)
    if pref and pref.raw != DEFAULT_PREFIX:
        out.append(f"{rel}: file-name prefix is {pref.raw!r}, expected {DEFAULT_PREFIX!r}")
    for si, sec in enumerate(cs.sections):
        for rid, r in sec.items():
            why = personal(rid, r.raw, cs.model)
            if why and any(r.raw):
                out.append(f"{rel} section {si} 0x{rid:04x}: unscrubbed personal value ({why})")
    return out


def help_problems(tracked: list) -> list:
    out = []
    for p, doc in definition_files():
        out += definition_help_problems(p, doc, tracked)
    return out


def definition_help_problems(p: Path, doc: dict, tracked: list) -> list:
    out = []
    rel = p.relative_to(ROOT).as_posix()
    why = help_files.refused(help_files.own_path(doc), doc)
    if why:          # another camera's help under this one's name: said once, not as every setting's text differing
        out.append(f"{paths.shown(help_files.own_path(doc))}: not this definition's help file: {why}")
    own = {} if why else help_files.read(help_files.own_path(doc), doc)
    for s in doc["settings"] if not why else []:
        mine = own.get(s["key"]) or {}
        for f in ("help", "option_help"):
            if s.get(f) and s[f] != mine.get(f):
                out.append(f"{rel} {s['key']} {f}: not the text of {help_files.own_path(doc).relative_to(ROOT)}")
    sony = help_files.read(help_files.PRIVATE / help_files.name(doc), doc)
    if not sony:
        return out
    theirs = set().union(*(runs(t) for _, t in texts(sony)))
    published = dict(texts(own))
    published.update((f"{s['key']} ({rel})", s["help"]) for s in doc["settings"] if s.get("help"))
    published.update((f"{s['key']} = {v} ({rel})", h) for s in doc["settings"] for v, h in (s.get("option_help") or []))
    for where, t in published.items():
        if runs(t) & theirs:
            out.append(f"{where}: shares {RUN} words in a row with the camera's In-Camera Guide text")
    names = menu_names(doc)
    for f in tracked:
        if not f.startswith(("data/", "docs/")):
            continue
        try:
            text = (ROOT / f).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out += guide_problems(f, text, theirs, names)
    for p in sorted((ROOT / "kit").rglob("*.py")):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out += guide_problems(str(p.relative_to(ROOT)), text, theirs, names, python=True)
    return out


def menu_names(doc: dict) -> set:
    """A definition's menu names of three words or more (guide_problems lets a shared run that holds one pass)."""
    # data/ and docs/ name the camera's settings all the time: a shared run that holds a whole menu name of three
    # words or more ("when Rec. Media dur HDMI Output is On") is the name, not Sony's prose
    return {n for n in (tuple(words(s.get("name") or "")) for s in doc.get("settings") or []) if len(n) >= 3}


def guide_problems(f: str, text: str, theirs: set, names: set, python: bool = None) -> list:
    """A file of data/ or docs/ (its text) that shares a run of eight words with the camera's In-Camera Guide text
    (`theirs`, its runs) but for a menu name (`names`), or a Python file's strings that do, each with its line;
    `python` tells a kit/ Python file (by default: its name ends in .py)."""
    if python is None:
        python = f.endswith(".py")
    if not python:
        def a_name(run: tuple) -> bool:
            return any(run[i:i + len(n)] == n for n in names for i in range(RUN - len(n) + 1))
        hit = any(not a_name(r) for r in runs(text) & theirs)
        return [f"{f}: shares {RUN} words in a row with the camera's In-Camera Guide text"] if hit else []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    return [f"{f}:{node.lineno}: shares {RUN} words in a row with the camera's In-Camera Guide text"
            for node in ast.walk(tree)
            if (isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value.split()) >= RUN
                and runs(node.value) & theirs)]


def problems(everything: bool = True) -> list:
    """Everything the guard refuses. everything=False reads the contents of the staged files only (a commit's);
    with nothing staged it reads them all."""
    if not (ROOT / "private").exists():
        print("note: private/ not present; skipping the checks that read it (the name, the addresses, Sony's help "
              "text); the generic ones still run", file=sys.stderr)
    tracked = git("ls-files", "-z")
    staged = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR")
    ignored = git("ls-files", "-z", "-ci", "--exclude-standard")
    out = path_problems(sorted(set(tracked) | set(staged)), ignored)
    home, owner = private_tokens()
    out += content_problems(tracked if everything or not staged else staged, home, owner)
    out += sample_problems(home, owner)
    out += lean_problems()
    out += data_problems()
    out += help_problems(tracked)
    return out


def data_problems() -> list:
    """Each file of a camera's data folder that carries what decision 16 keeps private (datafiles.evidence_in_public),
    place by place (the first five of each, and how many in all)."""
    out = []
    for d in datafiles.camera_folders(ROOT / "data"):
        for p in sorted(d.iterdir()):
            if not p.is_file() or p.suffix not in (".json", ".jsonl"):
                continue
            found = datafiles.evidence_in_public(p)
            rel = p.relative_to(ROOT).as_posix()
            if datafiles.kind_of(p) in datafiles.PRIVATE_WHOLE:
                out += [f"{rel}: {why}" for why in found]          # the one line, with the command that moves it
                continue
            where = ("the reset file is lean, by hand (docs/DATA_CONTRACTS.md, \"The reset file\")"
                     if datafiles.kind_of(p) == "settings_reset" else f"the kit keeps it in private/evidence/{d.name}/")
            out += [f"{rel}: carries evidence ({why}); {where}" for why in found[:5]]
            if len(found) > 5:
                out.append(f"{rel}: {len(found)} places of evidence in all")
    return out


def lean_problems() -> list:
    """Each definition that carries the mapping's evidence (definitions.evidence_in_public), place by place (the first
    five of each, and how many in all)."""
    out = []
    for p, doc in definition_files():
        found = definitions.evidence_in_public(doc, p.read_text(encoding="utf-8"))
        rel = p.relative_to(ROOT).as_posix()
        out += [f"{rel}: carries evidence ({why}); kit/schema_update.py --write keeps it in private/evidence/"
                for why in found[:5]]
        if len(found) > 5:
            out.append(f"{rel}: {len(found)} places of evidence in all")
    return out


def _git_bytes(*args, repo: Path = ROOT, stdin: bytes = None) -> bytes:
    """A git command's output as bytes, run in `repo` (fed `stdin`); stops in plain words when git fails (a range this
    clone does not hold)."""
    try:
        r = subprocess.run(["git", *args], cwd=repo, capture_output=True, input=stdin)
    except OSError as e:
        raise SystemExit(f"check_public: git is needed to read the commits ({e})") from None
    if r.returncode:
        raise SystemExit(f"check_public: git {' '.join(args)} failed: {r.stderr.decode('utf-8', 'replace').strip()}")
    return r.stdout


DATA_PATH = re.compile(r"data/([^/]+)/([^/]+\.jsonl?)")
DEFINITION_PATH = re.compile(r"editor/definitions/[^/]+\.json")


def blob_problems(path: str, text: str) -> list:
    """What a commit's version of `path` (its contents `text`) publishes that is private: a private-whole data file or
    one that is not lean (datafiles.evidence_in_public), a definition that carries evidence."""
    m = DATA_PATH.fullmatch(path)
    if m and paths.KEY.match(m.group(1)):
        return datafiles.evidence_in_public(Path(path), text)[:5]
    if DEFINITION_PATH.fullmatch(path):
        try:
            doc = json.loads(text)
        except ValueError:
            return []
        return definitions.evidence_in_public(doc, text)[:5] if isinstance(doc, dict) else []
    return []


def _changed(c: str, repo: Path) -> list:
    """[(path, mode, blob id)] of what commit `c` adds or changes, as git's raw diff gives them (-c: a merge's own
    paths, those that differ from every parent; what it brings from a parent in the range is that parent's commit's,
    read there, and from one outside it, such as the project's main, is public already). The new side is the last
    mode and the last id of each entry; a submodule (mode 160000) is kept, its id a commit, not a blob."""
    raw = _git_bytes("diff-tree", "-r", "-c", "--root", "--no-commit-id", "--no-abbrev", "-z", "--diff-filter=ACMRT",
                     c, repo=repo).decode("utf-8", "surrogateescape").split("\0")
    out, i = [], 0
    while i + 1 < len(raw):
        head, path = raw[i], raw[i + 1]
        i += 2
        if not head.startswith(":"):
            continue
        n = len(head) - len(head.lstrip(":"))          # one colon per parent
        fields = head.lstrip(":").split(" ")
        out.append((path, fields[n], fields[2 * n + 1]))
    return out


OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class Unreadable(Exception):
    """git's answer is not the object asked for, or not ended as git ends one: the stream is not to be trusted after
    it, so nothing more is read from it."""


class _Objects:
    """One long-lived git cat-file --batch: read(oid) gives one object's bytes, asked for by its id alone (never a
    <commit>:<path> name, which a path holding a newline would split into two requests), None for one git does not
    hold. Each answer's header must name the id asked for and the object must be followed by its newline, else
    Unreadable. Each is read when asked for and kept by no one here, so a range of many commits that each change a
    large file holds one version at a time."""

    def __init__(self, repo: Path):
        try:
            self.git = subprocess.Popen(["git", "cat-file", "--batch"], cwd=repo, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError as e:
            raise SystemExit(f"check_public: git is needed to read the commits ({e})") from None

    def read(self, oid: str):
        if not OBJECT_ID.fullmatch(oid or ""):
            raise Unreadable(f"{oid!r} is not an object id: objects are read by their ids alone")
        self.git.stdin.write(oid.encode("ascii") + b"\n")
        self.git.stdin.flush()
        header = self.git.stdout.readline()
        if not header:
            raise SystemExit("check_public: git cat-file --batch stopped answering")
        if not header.endswith(b"\n"):
            raise Unreadable(f"git's answer for {oid} is cut short")
        fields = header[:-1].split(b" ")
        if fields[0] != oid.encode("ascii"):
            raise Unreadable(f"git answered for {fields[0].decode('ascii', 'replace')!r} when {oid} was asked for")
        if fields[1:] == [b"missing"]:          # nothing follows
            return None
        if len(fields) != 3 or not fields[2].isdigit():
            raise Unreadable(f"git's answer for {oid} is not an object's header")
        size = int(fields[2])
        data = self.git.stdout.read(size)
        if len(data) != size or self.git.stdout.read(1) != b"\n":          # the newline after the object
            raise Unreadable(f"git's answer for {oid} does not end where its header says")
        return data

    def close(self):
        if self.git.stdin and not self.git.stdin.closed:
            self.git.stdin.close()
        self.git.stdout.close()
        self.git.wait()


NOT_READABLE = ("not readable: git does not hold this version (a shallow or partial clone); fetch the full history "
                "(git fetch --unshallow) and check again")


def _tree_blobs(commit: str, folder: str, repo: Path) -> list:
    """[(path, blob id)] of the files under `folder` in `commit`'s tree, from ls-tree -z (each entry "mode type
    id<TAB>path", NUL-ended: a path holding a newline stays one path); a submodule or a tree is left out."""
    out = []
    for entry in _git_bytes("ls-tree", "-r", "-z", commit, "--", folder, repo=repo).split(b"\0"):
        if not entry:
            continue
        meta, _, path = entry.partition(b"\t")
        fields = meta.split(b" ")
        if len(fields) == 3 and fields[1] == b"blob":
            out.append((path.decode("utf-8", "surrogateescape"), fields[2].decode("ascii")))
    return out


def _ignored(names: list, repo: Path) -> set:
    """The paths .gitignore (the clone's own, as checked out) ignores, whether or not they are tracked."""
    if not names:
        return set()
    try:
        r = subprocess.run(["git", "check-ignore", "--no-index", "-z", "--stdin"], cwd=repo, capture_output=True,
                           input=b"".join(n.encode("utf-8", "surrogateescape") + b"\0" for n in names))
    except OSError as e:
        raise SystemExit(f"check_public: git is needed to read the commits ({e})") from None
    if r.returncode not in (0, 1):          # 1: none of them ignored
        raise SystemExit(f"check_public: git check-ignore failed: {r.stderr.decode('utf-8', 'replace').strip()}")
    return {p for p in r.stdout.decode("utf-8", "surrogateescape").split("\0") if p}


def guide_runs() -> tuple:
    """(the runs of eight words of the camera's In-Camera Guide text in private/help/, the menu names of three words
    or more) over every definition of the tree; nothing when private/help/ is not here."""
    theirs, names = set(), set()
    for _, doc in definition_files():
        sony = help_files.read(help_files.PRIVATE / help_files.name(doc), doc)
        if sony:
            theirs |= set().union(*(runs(t) for _, t in texts(sony)))
            names |= menu_names(doc)
    return theirs, names


def commit_problems(spec: str, repo: Path = ROOT) -> list:
    """Each commit of the range `spec` (BASE..HEAD, oldest first) checked as --all checks the tree, on the files it
    adds or changes: the path rules (never published, Sony's SDK, a settings file no definition names as its sample, a
    spreadsheet, a file .gitignore ignores), the content rules (a binary file outside the published images and the
    samples, an image's metadata, a link's target, the leaks, a private/ path, private/'s own addresses and names, a
    sample's personal values), a data file or definition carrying what decision 16 keeps private (blob_problems) and
    the camera's In-Camera Guide text; a submodule (gitlink) by the path rules alone. Read from git's objects
    (diff-tree, one long-lived cat-file --batch, each blob read and judged in its turn and dropped after), nothing
    checked out: a pull request publishes every commit of its branch, not only its last tree. A version seen again at
    the same path (a revert) is not read or judged again. The samples are those the range's last commit's
    definitions name."""
    commits = _git_bytes("rev-list", "--reverse", spec, repo=repo).decode().split()
    if not commits:
        return []
    changed = {c: _changed(c, repo) for c in commits}
    last = commits[-1]
    defs = _tree_blobs(last, "editor/definitions/", repo)
    ignored = _ignored(sorted({f for c in commits for f, _, _ in changed[c]}), repo)
    home, owner = private_tokens()
    theirs, names = guide_runs()
    objects, judged, out = _Objects(repo), {}, []
    try:
        published = {}
        for n, blob in defs:
            if not DEFINITION_PATH.fullmatch(n) or CONTROL_RE.search(n):
                continue                              # a name with a control character: refused by its path
            data = objects.read(blob)
            if data is None:
                out.append(f"{last[:12]} {n}: {NOT_READABLE}")
                continue
            try:
                doc = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            s = definitions.sample(doc, Path(n)) if isinstance(doc, dict) else None
            if s is not None:
                published[s.as_posix()] = doc
        for c in commits:
            found = []
            for f, mode, blob in sorted(changed[c]):
                found += path_problems([f], [f] if f in ignored else [], published)
                if mode == "160000":                  # a submodule: a commit, no blob to read; its path is all it says
                    continue
                if (f, mode, blob) not in judged:     # the same version at the same path seen again costs nothing
                    data = objects.read(blob)
                    judged[(f, mode, blob)] = ([f"{f}: {NOT_READABLE}"] if data is None else
                                               blob_judged(f, mode, data, published, home, owner, theirs, names, repo))
                found += judged[(f, mode, blob)]
            out += [f"{c[:12]} {x}" for x in dict.fromkeys(found)]
    except Unreadable as e:
        out.append(f"check_public: git cat-file's answers can no longer be trusted ({e}); nothing after it was read, so "
                   "the range is not shown clean")
    finally:
        objects.close()
    if out:
        out.append("a pull request publishes every commit of its branch, so open it from a fresh branch cut from the "
                   "updated main with one commit of the final files (docs/UPDATING.md, \"Your pull request\")")
    return out


def blob_judged(f: str, mode: str, data: bytes, published: dict, home: set, owner: set, theirs: set, names: set,
                repo: Path) -> list:
    """The content rules over one version of a file in a commit (`data`, its blob), as commit_problems holds it: a
    link by its target, a file by file_problems, a sample by one_sample, a data file or definition by blob_problems,
    and the camera's In-Camera Guide text (`theirs`)."""
    if mode == "120000":                                         # a link: git publishes its target's name
        return link_problems(f, data.decode("utf-8", "surrogateescape"), home, owner, root=repo)
    found = file_problems(f, data, home, owner, published)
    if f in published:
        found += one_sample(f, data, published[f], home, owner)
    text = data.decode("utf-8", "replace")
    found += [f"{f}: {why}" for why in blob_problems(f, text)]
    if theirs and (f.startswith(("data/", "docs/")) or (f.startswith("kit/") and f.endswith(".py"))):
        found += guide_problems(f, text, theirs, names)
    if theirs and DEFINITION_PATH.fullmatch(f):
        found += definition_guide_problems(f, text, theirs)
    return found


def definition_guide_problems(f: str, text: str, theirs: set) -> list:
    """Each help text of a definition (its text) that shares a run of eight words with the camera's In-Camera Guide
    text (`theirs`)."""
    try:
        doc = json.loads(text)
    except ValueError:
        return []
    settings = doc.get("settings") if isinstance(doc, dict) else None
    out = []
    for s in settings if isinstance(settings, list) else []:
        if not isinstance(s, dict):
            continue
        helps = ([(s.get("key"), s["help"])] if isinstance(s.get("help"), str) else [])
        helps += [(f"{s.get('key')} = {v}", h) for v, h in (s.get("option_help") or []) if isinstance(h, str)]
        out += [f"{f} {where}: shares {RUN} words in a row with the camera's In-Camera Guide text"
                for where, h in helps if runs(h) & theirs]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="read every tracked file's contents, not only the staged ones")
    ap.add_argument("--commits", metavar="BASE..HEAD",
                    help="only check every commit of this range (a pull request's): the files each adds or changes, "
                         "by the path and content rules --all reads the tree by")
    a = ap.parse_args()
    if a.commits:
        found = commit_problems(a.commits)
        for p in found:
            print(p)
        sys.exit(1 if found else 0)
    found = problems(everything=a.all)
    for p in found:
        print(p)
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
