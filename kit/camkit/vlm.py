"""Vision-language readers: OpenAI-compatible servers (the local omlx, vLLM on the LAN, or a hosted
service with "api_key_env") and Claude (camkit.claude_reader), in parallel.

Each reader answers the same question about the same frame; the callers decide what the readers agree on (a label two
sources read alike: page_model.py's vote, pass1_map.py, tiebreak.py) and flag the rest for review.
Answers are cached under the camera's runs (runs/<model>_fw<fw>/_cache/vlm) by image + prompt + model, so re-reads
are free (cache_key, cached, keep: every reader keeps its answers the same way).
Readers and endpoints come from private/config.json ("readers"). A camera run that asks a reader checks that it lists
one before it opens the link (check_readers); inside a run a missing reader is an ordinary exception (NoReader).

Every question a run asks about a frame goes through ask_role, which takes up a stand-in when the reader playing the
role will not connect. The batch tools that read a whole run's frames afterwards build their readers themselves
(make_reader) and get no stand-in: kit/tiebreak.py, kit/pass1_labels.py, kit/page_model.py and kit/help_reads.py.
"""
import base64
import contextlib
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import ConfigMissing, config, paths

CACHE = None          # the answers' folder when set (the tests); else the camera's, cache_dir()


def cache_dir() -> Path:
    """runs/<model>_fw<fw>/_cache/vlm: the readers' answers, beside the camera's runs (camkit.paths)."""
    return Path(CACHE) if CACHE is not None else paths.run_root() / "_cache" / "vlm"


def cache_key(image: bytes, prompt: str, model: str) -> str:
    """The name an answer is kept under: the frame's bytes, the question and the model."""
    return hashlib.sha1(image + prompt.encode() + model.encode()).hexdigest()


def cached(key: str) -> dict | None:
    """The answer kept under key, or None: none kept, or a file a crash or another thread left unreadable (asked
    again). An answer that was not JSON is never kept (keep), and is asked again if an older kit kept one."""
    try:
        answer = json.loads((cache_dir() / f"{key}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return answer if isinstance(answer, dict) and "_unparsed" not in answer else None


def keep(key: str, answer: dict) -> dict:
    """The answer, kept under key unless it was not JSON (a garbled answer is asked again next time). Written whole or
    not at all: readers ask in parallel, and two threads can keep the same frame's answer at once. The cache is best
    effort: a write that fails (a full disk; on Windows, replacing a file another thread is reading) keeps nothing and
    leaves no part file, and the answer, paid for with a hosted reader, still goes back to the caller."""
    if "_unparsed" in answer:
        return answer
    f = cache_dir() / f"{key}.json"
    part = f.with_name(f"{f.name}.{os.getpid()}.{threading.get_ident()}.part")
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        part.write_text(json.dumps(answer), encoding="utf-8")
        part.replace(f)
    except OSError:
        with contextlib.suppress(OSError):
            part.unlink()
    return answer


PROMPTS = {
    "dialog": (
        "This is a Sony camera menu screen showing one setting's options. Reply with JSON only:\n"
        '{"title": the white title at the top, "selected": the full orange text line under the title '
        '(the selected option\'s name), "values": any other value text visible (list), '
        '"footer": the button labels in the bottom bar (list)}'),
    "menu": (
        "This is a Sony camera menu page. Reply with JSON only:\n"
        '{"breadcrumb": the text at the top left, "page": the n/N page counter at the top right, '
        '"rows": [{"label": row label, "value": value shown at the right or "", '
        '"greyed": true if the row text is grey, "highlighted": true for the row with the orange bar}]}'),
    "notice": (
        "This is a message on a Sony camera screen. Reply with JSON only:\n"
        '{"text": the full message text, "buttons": button labels (list)}'),
    "option": (
        "This is a Sony camera settings screen. Reply with JSON only:\n"
        '{"title": the title of the screen, "selected": the exact text of the item under the CURSOR: '
        'the item on the orange bar, or in the orange box, or the orange line under the title. A radio '
        'button with an orange dot marks the SAVED value, which can be a different item: do not use it. '
        '"value": the value shown with the cursor item, or ""}'),
    "fields": (
        "This is a Sony camera number-entry screen. Reply with JSON only:\n"
        '{"title": the title, "fields": [the value in each box, left to right, with its unit], '
        '"active": index of the orange box}'),
    "any": (
        "Describe this Sony camera screen. Reply with JSON only:\n"
        '{"kind": one of menu_page | dialog | checkbox_list | number_fields | grid | tiles | notice | '
        'shooting | playback | keyboard | other, "title": main title text, "selected": highlighted item text, '
        '"text": all other visible text (list)}'),
}


def make_reader(cfg: dict, **override):
    """The reader a private/config.json "readers" entry describes: "kind": "anthropic" is Claude
    (camkit.claude_reader), anything else an OpenAI-compatible /v1 server (Reader)."""
    cfg = {**cfg, **override}
    if cfg.get("kind") == "anthropic":
        from .claude_reader import ClaudeReader
        return ClaudeReader(**cfg)
    return Reader(**cfg)


NO_READER = ("private/config.json lists no reader: copy the ones you choose from \"readers_examples\" into \"readers\" "
             "(docs/QUICKSTART.md, \"Choosing a reader\")")


class NoReader(LookupError):
    """No reader to ask: private/config.json lists none (kit/config.example.json lists none, so a copy of it asks no
    server anything until its owner has chosen one, 2026-11-13), or none for a role. An ordinary exception, never a
    SystemExit: inside a camera run every caller of a reader takes it as a reader that could not answer, as it took the
    IndexError and KeyError this was before, so the run's own cleanup and restore go on as ever. A camera run that
    asks a reader finds a missing list before it opens the link (check_readers), and the batch tools with no camera
    stop on it with its message (readers(stop=True))."""


def _settings() -> dict:
    """private/config.json, or {} when there is none: a missing file is a missing reader list here (NoReader), never a
    ConfigMissing (a SystemExit) in the middle of a run."""
    try:
        return config()
    except ConfigMissing:
        return {}


def readers(stop: bool = False, settings: dict | None = None) -> list:
    """The readers private/config.json lists ("readers"), or `settings` (the config a caller has read already). None
    listed raises NoReader, saying what to do; stop: raises ConfigMissing instead, which ends the program with that
    sentence (the batch tools with no camera, and check_readers), and no private/config.json at all ends it with
    config()'s own."""
    if settings is None:
        settings = config() if stop else _settings()
    listed = settings.get("readers") or []
    if not listed:
        raise (ConfigMissing if stop else NoReader)(NO_READER)
    return listed


def check_readers() -> None:
    """Called by every camera run that asks a reader (each one that builds a LiveCamera, and runner.prover_session
    for the provers) before it opens the link: a config that lists no reader, or no config at all, stops the run
    there, with what to do, before anything is pressed or downloaded. Such a run went on with OCR alone until
    2026-11-13, each reader's question failing as it came. A run that asks none (page_scan, selftest, identify) and a
    restore (mode_switch --restore, pass 3's, prove_run's start file put back with nothing to prove) never check."""
    readers(stop=True)


def role(name: str) -> dict:
    """The config entry that plays a role: "second" (the second reading beside OCR, asked on every
    proof) or "third" (the tie-breaker where OCR and the second disagree). private/config.json "roles"
    names a reader for each ({"second": "claude"}); without it, the first and second readers listed. No reader for
    the role raises NoReader, an ordinary exception (see there)."""
    c = _settings()
    listed = readers(settings=c)
    named = c.get("roles", {}).get(name)
    if named:
        found = next((r for r in listed if r["name"] == named), None)
        if found is None:
            raise ValueError(f"private/config.json: \"roles\" gives the {name} role to {named!r}, which no entry of "
                             f"\"readers\" names ({', '.join(repr(r['name']) for r in listed)})")
        return found
    at = {"second": 0, "third": 1}[name]
    if at >= len(listed):
        raise NoReader(f"private/config.json lists one reader, and the {name} role needs another: add one to "
                       f"\"readers\", or name the reader for it in \"roles\" (docs/QUICKSTART.md, step 3)")
    return listed[at]


_STANDING_IN: dict = {}        # role -> the reader config standing in for one that would not connect, or given it


def assign_role(name: str, cfg: dict) -> None:
    """Give a role ("second", "third") to a configured reader for the rest of the process, as a stand-in is given one
    (kit/tools/reread_proofs.py --reader NAME)."""
    _STANDING_IN[name] = cfg


def standing_in(name: str) -> dict | None:
    """The config entry given a role for the process (assign_role) or standing in for it (stand_in), or None."""
    return _STANDING_IN.get(name)


def playing(name: str) -> dict:
    """The config entry playing a role now: the one given it or standing in (standing_in), else role()."""
    return standing_in(name) or role(name)


def reader_for(name: str, **override):
    """The reader playing a role (`role`), or, once that one has failed to connect, the next configured reader that
    answers, remembered for the process: a server on another machine switched off must not cost every proof its
    reading (2026-11-06). A hosted reader ("kind": "anthropic") is never chosen as a stand-in by itself: it costs
    money, so it stands in only when the config names it for the role."""
    return make_reader(playing(name), **override)


def stand_in(name: str, failed: dict) -> dict | None:
    """After `failed` would not connect: the next local reader that answers a tiny request, kept for the role."""
    for r in readers():
        if r["name"] == failed.get("name") or r.get("kind") == "anthropic":
            continue
        try:
            make_reader(r, timeout=20).ping()
        except Exception:
            continue
        _STANDING_IN[name] = r
        print(f"reader {failed.get('name')!r} does not answer: {r['name']!r} stands in", flush=True)
        return r
    return None


def ask_role(name: str, image: bytes, prompt: str, timeout: float) -> dict:
    """The answer of the reader playing a role ("second", "third"); when it will not connect, the next configured
    reader that answers takes the role for the rest of the run (stand_in): the remote server was off, 2026-11-06.
    Every question a run asks about a frame comes here (proving.screens.ask_second, camkit.live's reader_label and
    submenu_labels); the batch tools the module docstring names are the exception."""
    try:
        return reader_for(name, timeout=timeout).ask(image, prompt)
    except urllib.error.URLError:
        if standing_in(name) is not None or stand_in(name, role(name)) is None:
            raise
        return reader_for(name, timeout=max(timeout, 60)).ask(image, prompt)


class Reader:
    def __init__(self, name, url, model, parallel=1, timeout=120, kind=None, api_key_env=None, **_):
        self.name, self.url, self.model, self.timeout = name, url.rstrip("/"), model, timeout
        self.api_key_env = api_key_env
        self.slots = threading.Semaphore(parallel)

    def headers(self) -> dict:
        """A hosted service's entry names, in "api_key_env", the environment variable holding its key. The
        key is read from it here, when a request is sent, and goes only into that request's Authorization
        header: never into the config, the cache or a run (2026-11-04). A local server needs no key."""
        headers = {"Content-Type": "application/json"}
        if self.api_key_env:
            key = os.environ.get(self.api_key_env)
            if not key:
                raise RuntimeError(f"reader {self.name}: the environment variable {self.api_key_env} is not set")
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def ping(self):
        """A tiny request, to tell a server that answers from one that is off."""
        body = {"model": self.model, "max_tokens": 3, "messages": [{"role": "user", "content": "OK"}],
                "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request(self.url + "/chat/completions", json.dumps(body).encode(), self.headers())
        with urllib.request.urlopen(req, timeout=self.timeout) as reply:
            reply.read()

    def ask(self, image: bytes, prompt: str) -> dict:
        key = cache_key(image, prompt, self.model)
        answer = cached(key)
        if answer is not None:
            return answer
        body = {
            "model": self.model, "temperature": 0, "max_tokens": 800,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image).decode()}},
                {"type": "text", "text": prompt}]}],
        }
        req = urllib.request.Request(self.url + "/chat/completions", json.dumps(body).encode(), self.headers())
        with self.slots:
            for wait in (2, 5, 15, None):
                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as r:
                        reply = json.load(r)
                    break
                except urllib.error.HTTPError as e:
                    # 502/503/504: the gateway is busy or swapping models (2026-10-28); retry, then give up
                    if e.code not in (502, 503, 504) or wait is None:
                        raise
                    time.sleep(wait)
        # a reasoning server can answer with no content at all ("content": null): that is no JSON, asked again
        return keep(key, parse_json(reply["choices"][0]["message"].get("content") or ""))


def parse_json(text: str) -> dict:
    """The JSON object in a model's answer (tolerates ``` fences and surrounding prose)."""
    text = text or ""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"_unparsed": text}
    try:
        return json.loads(m.group(0))
    except ValueError:
        return {"_unparsed": text}
