"""The readers' start check (camkit.vlm.check_readers, start_check, verdict) and kit/tools/reader_check.py, with no
network: the readers' server is a stub of urllib.request.urlopen that answers each reader's address as the test says,
and Claude a stub of its client. The run-level guarantees (a run whose readers do not answer presses nothing, the
restores need none) are in kit/tests/test_scripts.py beside the other start checks."""
import base64
import io
import json
import threading
import urllib.error
import urllib.request

import pytest

import camkit
from camkit import vlm
from camkit.runs import Run


def server(said: dict, sent: list):
    """urlopen for readers at http://127.0.0.1:<port>/v1: each port's reply from said, by the reader's port: a dict (the
    chat answer's content, as JSON), a str (the content as is), a (dict, model) pair (the server names the model that
    answered), an exception to raise, or a function giving one (a fresh HTTP error each time: its body is read once)."""
    def urlopen(req, timeout=None):
        sent.append(req)
        port = int(req.full_url.split(":")[2].split("/")[0])
        reply = said[port]
        reply = reply() if callable(reply) else reply
        if isinstance(reply, BaseException):
            raise reply
        reply, model = reply if isinstance(reply, tuple) else (reply, None)
        content = reply if isinstance(reply, str) else json.dumps(reply)
        body = {"choices": [{"message": {"content": content}}], **({"model": model} if model else {})}
        return io.BytesIO(json.dumps(body).encode())
    return urlopen


def http_error(port: int, code: int, reason: str, message: str) -> urllib.error.HTTPError:
    body = json.dumps({"error": {"message": message, "type": "server_error", "code": code}}).encode()
    return urllib.error.HTTPError(f"http://127.0.0.1:{port}/v1/chat/completions", code, reason, {}, io.BytesIO(body))


def local(name: str, port: int, model: str = "m") -> dict:
    return {"name": name, "url": f"http://127.0.0.1:{port}/v1", "model": model}


def hosted(name: str, port: int) -> dict:
    return {**local(name, port, "hosted-model"), "api_key_env": "CAMSET_TEST_READER_KEY"}


LEAKY = ("bad key sk-abcdef123456 for http://127.0.0.1:8007/v1 from 203.0.113.7 and nas.local, models in "
         "/Users/you/models, key sk-test, reply to someone@example.org")
ANSWERS = {8001: {"text": "MENU 42", "buttons": []},
           8002: lambda: http_error(8002, 507, "Insufficient Storage",
                                    "Insufficient Storage: the model needs more memory than is free"),
           8003: urllib.error.URLError(TimeoutError("timed out")),
           8004: {"text": "MENU 4Z", "buttons": []},
           8005: "MENU 42",
           8006: {"text": "Menu42"},
           8007: lambda: http_error(8007, 401, "Unauthorized", LEAKY),
           8008: ({"text": "MENU 42"}, "/Users/you/weights/Served-VL-8B"),
           8009: {"text": "MENU 420"},
           8010: {"text": "SUBMENU 42"}}


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A private/config.json of the test's own (write(readers, roles)), the readers' stub server (sent: every request),
    the answers' cache in a folder of the test's own, and the paid reader's key set."""
    sent = []
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "config.json")
    monkeypatch.setattr(urllib.request, "urlopen", server(ANSWERS, sent))
    monkeypatch.setattr(vlm, "CACHE", tmp_path / "cache")
    monkeypatch.setenv("CAMSET_TEST_READER_KEY", "sk-test")
    vlm.forget()

    def write(readers, roles=None):
        camkit.CONFIG.write_text(json.dumps({"readers": readers, **({"roles": roles} if roles else {})}),
                                 encoding="utf-8")
        sent.clear()
    yield write, sent
    vlm.forget()


def ports(sent) -> list:
    return sorted(int(r.full_url.split(":")[2].split("/")[0]) for r in sent)


def test_each_reader_is_asked_a_real_question_and_its_answer_read(world, tmp_path):
    """A reader that answers; one that answers HTTP 507 with a JSON error body; one that times out; one that reads the
    wrong text; one that answers with no JSON object. Each is asked through a run's own request (its endpoint, its
    model, a picture and a run's question), nothing is taken from or kept in the answers' cache, and each failure says
    what happened in words: the HTTP status with the server's own short message, the timeout, what it read."""
    write, sent = world
    write([local("good", 8001, "Qwen-VL"), local("full", 8002), local("slow", 8003), local("wrong", 8004),
           local("prose", 8005)])
    image = vlm.check_picture()
    key = vlm.cache_key(image, vlm.PROMPTS[vlm.CHECK_PROMPT], "Qwen-VL")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / f"{key}.json").write_text('{"text": "MENU 42"}', encoding="utf-8")   # never used
    checks = {c.name: c for c in vlm.start_check()}
    assert checks["good"].ok and checks["good"].said == "MENU 42" and checks["good"].roles == ("second",)
    assert checks["full"].error == ("HTTP 507 Insufficient Storage: Insufficient Storage: the model needs more memory "
                                    "than is free") and checks["full"].roles == ("third",)
    assert checks["slow"].error == "no answer within 25 s (timed out)"
    assert checks["wrong"].error == "it read 'MENU 4Z' where the picture says 'MENU 42'"
    assert checks["prose"].error == "its answer was no JSON object: 'MENU 42'"
    assert not any(checks[n].ok for n in ("full", "slow", "wrong", "prose"))
    assert all(c.asked and c.seconds is not None and c.kind == "openai-compatible" for c in checks.values())
    asked = [r for r in sent if ":8001/" in r.full_url]
    assert len(asked) == 1 and asked[0].full_url == "http://127.0.0.1:8001/v1/chat/completions"
    body = json.loads(asked[0].data)
    assert body["model"] == "Qwen-VL" and body["temperature"] == 0
    picture, question = body["messages"][0]["content"]
    assert question == {"type": "text", "text": vlm.PROMPTS["notice"]}
    png = base64.b64decode(picture["image_url"]["url"].split(",", 1)[1])
    assert png == image and png[:8] == b"\x89PNG\r\n\x1a\n"
    from PIL import Image
    assert Image.open(io.BytesIO(png)).size == (640, 480)
    assert [p.name for p in (tmp_path / "cache").iterdir()] == [f"{key}.json"]        # nothing kept


def test_the_answer_must_read_the_picture_and_nothing_more(world):
    """The answer's "text" read for the picture's words alone, case, spacing and signs aside; with no "text", all its
    texts joined: "MENU 420" and "SUBMENU 42" are not "MENU 42"."""
    assert vlm.reads_check_text({"text": "Menu42"}) and vlm.reads_check_text({"text": " MENU-42. "})
    assert vlm.reads_check_text({"lines": ["MENU", "42"]}) and vlm.reads_check_text({"message": "menu 42"})
    for wrong in ({"text": "MENU 420"}, {"text": "SUBMENU 42"}, {"text": "MENU 4"}, {}, {"lines": ["MENU 42", "OK"]},
                  {"text": "MENU 42 OK"}):
        assert not vlm.reads_check_text(wrong), wrong
    write, _ = world
    write([local("long", 8009), local("sub", 8010)])
    checks = {c.name: c for c in vlm.start_check()}
    assert checks["long"].error == "it read 'MENU 420' where the picture says 'MENU 42'"
    assert checks["sub"].error == "it read 'SUBMENU 42' where the picture says 'MENU 42'" and not checks["sub"].ok


def test_a_healthy_config_starts_as_it_did_and_says_so_in_a_line(world, capsys):
    write, sent = world
    write([local("vllm", 8001), local("omlx", 8006)])
    checks = vlm.check_readers()
    assert [c.ok for c in checks] == [True, True] and ports(sent) == [8001, 8006]
    said = capsys.readouterr().out
    assert said.startswith("readers: 'vllm' (second reader) answered in ") and "'omlx' (third reader) answered" in said
    assert vlm.standing_in("second") is None and vlm.standing_in("third") is None      # each plays its own role
    assert vlm.playing("second")["name"] == "vllm" and "http" not in said
    assert vlm.check_readers() == checks and len(sent) == 2                              # once per process


def test_no_reader_answering_stops_the_run_naming_each_and_what_to_do(world):
    write, sent = world
    write([local("vllm", 8003), local("omlx", 8002)])
    with pytest.raises(camkit.ConfigMissing) as stop:
        vlm.check_readers()
    said = str(stop.value)
    assert said.startswith("The start check: no reader answered, so this run stops before it opens the camera link, "
                           "and nothing is pressed")
    assert "  'vllm' (second reader): did not answer right: no answer within 25 s (timed out)\n" in said
    assert ("  'omlx' (third reader): did not answer right: HTTP 507 Insufficient Storage: Insufficient Storage: the "
            "model needs more memory than is free\n") in said
    assert "kit/tools/reader_check.py" in said and "127.0.0.1" not in said
    assert vlm._CHECKED is None                                  # asked again next time, nothing remembered


def test_a_reader_that_does_not_answer_is_skipped_and_one_that_answers_stands_in(world, capsys):
    write, sent = world
    write([local("remote", 8002), local("omlx", 8001)])
    vlm.check_readers()
    said = capsys.readouterr().out
    assert vlm.standing_in("second")["name"] == "omlx" and vlm.playing("second")["name"] == "omlx"
    assert "'remote' (second reader) did not answer right: HTTP 507 Insufficient Storage" in said
    assert "reader 'remote' does not answer: 'omlx' stands in as the second reader for this run" in said
    assert "remote" in vlm._SKIPPED
    assert vlm.stand_in("third", {"name": "omlx"}) is None                # never brought back in during the run


def test_a_paid_second_reader_is_always_asked_and_a_local_one_stands_in_when_it_fails(world, monkeypatch, capsys):
    """The playbook's own example gives Claude the second role and a local reader the third: the paid second reader is
    asked at the start even when the local one answers (a run asks it on every proof), and one whose key is not set
    is found there: the local reader stands in for it, said, rather than the run going on with OCR alone."""
    write, sent = world
    write([local("omlx", 8001), hosted("openai", 8006)], roles={"second": "openai", "third": "omlx"})
    checks = {c.name: c for c in vlm.check_readers()}
    assert ports(sent) == [8001, 8006] and checks["openai"].ok and checks["openai"].roles == ("second",)
    assert vlm.standing_in("second") is None
    vlm.forget()
    capsys.readouterr()
    monkeypatch.delenv("CAMSET_TEST_READER_KEY")
    write([local("omlx", 8001), hosted("openai", 8006)], roles={"second": "openai", "third": "omlx"})
    checks = {c.name: c for c in vlm.check_readers()}
    said = capsys.readouterr().out
    assert checks["openai"].error == "RuntimeError: reader openai: the environment variable CAMSET_TEST_READER_KEY is not set"
    assert vlm.playing("second")["name"] == "omlx" and ports(sent) == [8001]
    assert "reader 'openai' does not answer: 'omlx' stands in as the second reader for this run" in said
    vlm.forget()
    write([local("omlx", 8002), hosted("openai", 8006)], roles={"second": "openai", "third": "omlx"})
    with pytest.raises(camkit.ConfigMissing, match="no reader answered, so this run stops"):
        vlm.check_readers()


def test_a_paid_reader_never_stands_in_and_a_third_one_is_asked_only_when_no_local_one_answered(world, capsys):
    """A paid reader plays only the roles the config gives it. As the third reader (listed second) it is not asked while
    a local reader answers; with none answering it is asked (said first), but its answer cannot take the second
    role: the run stops, saying it is paid and how to give it the role. One that plays no role is never asked."""
    write, sent = world
    write([local("omlx", 8001), hosted("openai", 8006)])
    checks = {c.name: c for c in vlm.check_readers()}
    assert ports(sent) == [8001] and not checks["openai"].asked and checks["openai"].roles == ("third",)
    assert checks["openai"].not_asked.startswith("paid, and a local reader answered") and checks["openai"].paid
    vlm.forget()
    capsys.readouterr()
    write([local("omlx", 8002), hosted("openai", 8006)])
    with pytest.raises(camkit.ConfigMissing) as stop:
        vlm.check_readers()
    said = str(stop.value)
    assert "no local reader answered: asking the paid third reader 'openai' (each question costs money)" in capsys.readouterr().out
    assert ports(sent) == [8002, 8006] and vlm.standing_in("second") is None
    assert ("the second reader, 'omlx', did not answer, and no local reader answered to stand in for it ('openai' "
            "answered); 'openai' is a paid reader listed but not given the second role, and a paid reader never stands "
            "in for another: to pay for it as the second reader, give it the role in private/config.json, \"roles\": "
            "{\"second\": \"openai\"}") in said
    vlm.forget()
    write([local("vllm", 8003), local("omlx", 8002), hosted("openai", 8006)])
    with pytest.raises(camkit.ConfigMissing) as stop:
        vlm.check_readers()
    assert ports(sent) == [8002, 8003] and "'openai' (paid): not asked: a run never asks it" in str(stop.value)
    assert "no reader answered; 'openai' is a paid reader listed but not given the second role" in str(stop.value)
    assert not vlm.may_stand_in(hosted("openai", 8006)) and not vlm.may_stand_in({"name": "c", "kind": "anthropic"})
    assert vlm.may_stand_in(local("omlx", 8001))


def test_a_paid_reader_is_never_brought_in_during_the_run(world, monkeypatch):
    """stand_in, after the second reader fails to connect during the run: a local reader that answers, never a paid one
    the config gave no role."""
    write, _ = world
    write([local("remote", 8003), hosted("openai", 8006), local("omlx", 8001)])
    pinged = []
    monkeypatch.setattr(vlm.Reader, "ping", lambda self: pinged.append(self.name))
    assert vlm.stand_in("second", {"name": "remote"})["name"] == "omlx" and pinged == ["omlx"]


def test_claude_is_asked_only_where_a_run_would_ask_it(world, monkeypatch, capsys):
    """Claude ("kind": "anthropic") plays a role or is never asked by a run (it stands in for no other reader); as the
    second reader it is asked with the local ones; as the third only when no local reader answered."""
    from camkit import claude_reader
    write, sent = world
    asked = []

    class Claude:
        def __init__(self, name, timeout=None, **_):
            self.name = name

        def answer(self, image, prompt, waits=None):
            asked.append(self.name)
            self.served = "claude-opus-5-5"
            return {"text": "MENU 42"}
    monkeypatch.setattr(claude_reader, "ClaudeReader", Claude)
    claude = {"name": "claude", "kind": "anthropic", "model": "claude-opus-5-5"}
    write([local("vllm", 8001), local("omlx", 8006), claude])
    checks = {c.name: c for c in vlm.check_readers()}
    assert asked == [] and checks["claude"].not_asked.startswith("a run never asks it")
    vlm.forget()
    write([local("vllm", 8002), claude])                       # Claude the third reader, the second gone
    with pytest.raises(camkit.ConfigMissing, match="the second reader, 'vllm', did not answer, and no local reader "
                                                   "answered to stand in for it \\('claude' answered\\)"):
        vlm.check_readers()
    assert asked == ["claude"] and "asking the paid third reader 'claude'" in capsys.readouterr().out
    vlm.forget()
    write([local("vllm", 8001), claude], roles={"second": "claude", "third": "vllm"})
    checks = vlm.check_readers()
    assert {c.name: c.ok for c in checks} == {"vllm": True, "claude": True} and asked == ["claude", "claude"]
    assert all(not c.served for c in checks)                   # the server named the configured model


def test_a_third_reader_that_did_not_answer_is_not_asked_during_the_run(world, monkeypatch, capsys):
    """A role whose reader failed the start check, with no local reader to stand in for it, goes unanswered for the
    run: each question to it is no answer at once (NoReader, which every caller takes as no answer), asking nothing,
    where it cost every tie-break the full timeout."""
    from camkit import claude_reader

    class Claude:
        def __init__(self, name, timeout=None, **_):
            pass

        def answer(self, image, prompt, waits=None):
            return {"text": "MENU 42"}
    monkeypatch.setattr(claude_reader, "ClaudeReader", Claude)
    write, sent = world
    write([{"name": "claude", "kind": "anthropic", "model": "claude-opus-5-5"}, local("omlx", 8002)],
          roles={"second": "claude", "third": "omlx"})
    vlm.check_readers()
    said = capsys.readouterr().out
    assert ("reader 'omlx' does not answer and no local reader may stand in: the third reader's questions go "
            "unanswered for this run") in said
    sent.clear()
    with pytest.raises(vlm.NoReader, match="'omlx' did not answer the run's start check"):
        vlm.ask_role("third", b"a frame", "prompt", 25)
    assert sent == [] and "failed during the run" not in capsys.readouterr().err


def test_a_role_naming_no_reader_or_an_entry_with_no_name_stops_the_run_at_its_start(world):
    write, _ = world
    write([local("omlx", 8001)], roles={"second": "claude"})
    with pytest.raises(camkit.ConfigMissing, match="gives the second role to 'claude', which no entry"):
        vlm.check_readers()
    for readers, why in (([local("omlx", 8001), {"url": "http://127.0.0.1:8006/v1", "model": "m"}],
                          "entry 2 of \"readers\" has no \"name\""),
                         ([local("omlx", 8001), local("omlx", 8006)], "two entries of \"readers\" have the name 'omlx'"),
                         ([local("omlx", 8001), "omlx"], "entry 2 of \"readers\" is not an object")):
        write(readers)
        with pytest.raises(camkit.ConfigMissing) as stop:
            vlm.check_readers()
        assert str(stop.value).startswith(f"private/config.json: {why}: each reader is an object") and "127.0" not in str(stop.value)


def test_a_reader_failing_during_the_run_is_said_once_and_logged(world, tmp_path, capsys):
    """A reader that passed the start check and fails later: each question still fails to its caller as before (the
    run goes on with OCR alone or a stand-in), and the failure is said once per reader in the run, on standard error and
    in the run's events.jsonl, not once per question, with no address or key in either."""
    write, _ = world
    write([{**local("omlx", 8007), "api_key_env": "CAMSET_TEST_READER_KEY"}])
    run = Run("kit2_test", root=tmp_path / "runs")
    vlm.log_to(run)
    for _ in range(3):
        with pytest.raises(urllib.error.HTTPError):
            vlm.ask_role("second", b"a frame", "prompt", 5)
    err = capsys.readouterr().err
    assert err.count("reader 'omlx' failed during the run (HTTP 401 Unauthorized: bad key <key> for <address>") == 1
    events = [json.loads(line) for line in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(e["kind"], e["reader"]) for e in events] == [("reader_failing", "omlx")]
    for text in (err, events[0]["why"]):
        for leak in ("sk-abcdef", "127.0.0.1", "8007", "203.0.113.7", "nas.local", "/Users/you", "sk-test", "someone@"):
            assert leak not in text, (leak, text)


# ---------------------------------------------------------------------------------------------- what is printed

def test_no_address_key_or_folder_is_printed(world):
    """A url with no scheme is refused by the reader's entry, naming no address, and nothing is sent; a server's own
    message is scrubbed of every configured address, the key the reader's variable holds, and anything that looks like
    an address, a key, an e-mail address or a home folder; a model id that is a path shows its last part."""
    write, sent = world
    write([{"name": "bare", "url": "127.0.0.1:8001/v1", "model": "m"}, {"name": "none", "model": "m"},
           {**local("leaky", 8007, "/Users/you/models/Qwen-VL"), "api_key_env": "CAMSET_TEST_READER_KEY"}])
    checks = {c.name: c for c in vlm.start_check(ask_paid="all")}
    assert checks["bare"].error == "its \"url\" in private/config.json does not start with http:// or https://"
    assert checks["none"].error == "its entry in private/config.json has no \"url\""
    assert ports(sent) == [8007] and checks["leaky"].model == "Qwen-VL"
    error = checks["leaky"].error
    assert error == ("HTTP 401 Unauthorized: bad key <key> for <address> from <address> and <address>, models in "
                     "<home>/models, key <key>, reply to <e-mail>"), error
    assert vlm.scrub("fe80::1%en0 and 2001:db8::7 at 12:30:45, AA:BB:CC:DD:EE:FF", listed=[]) == (
        "<address> and <address> at 12:30:45, <address>")
    assert vlm.scrub("Bearer abc.def and a token " + "x" * 40, listed=[]) == "<key> and a token <key>"
    assert vlm.scrub(r"C:\Users\you\models", listed=[]) == r"<home>\models"
    assert vlm.shown_model("RedHatAI/Qwen3.8-27B-INT4") == "Qwen3.8-27B-INT4" and vlm.shown_model("m") == "m"


def test_a_long_model_id_is_no_key_and_two_long_ids_are_told_apart(world, capsys):
    """A model id is words joined by hyphens or underscores, never a key, however long: it is printed as it is, in the
    table and in a server's message. A key is an unbroken run; the configured ids and the server's are never taken for
    one, and the server's model is compared with the configured one raw, before anything is printed."""
    import reader_check
    long_id = "Qwen3-VL-30B-A3B-Instruct-AWQ-4bit"
    other = "Qwen3-VL-30B-A3B-Instruct-AWQ-8bit"
    unbroken = "A" * 20 + "7" * 20                                   # a configured id that is one unbroken run
    assert vlm.scrub(f"The model `{long_id}` does not exist.", listed=[]) == f"The model `{long_id}` does not exist."
    assert vlm.scrub("key " + "Ab3" * 12, listed=[]) == "key <key>" and vlm.shown_model(long_id) == long_id
    assert vlm.scrub(f"model {unbroken} gone", listed=[local("x", 8001, unbroken)]) == f"model {unbroken} gone"
    assert vlm.scrub(f"model {unbroken} gone", listed=[]) == "model <key> gone"
    assert vlm.scrub(f"answered by {unbroken}", listed=[], keep=(unbroken,)) == f"answered by {unbroken}"
    write, _ = world
    ANSWERS[8011] = ({"text": "MENU 42"}, other)
    try:
        write([local("vllm", 8011, long_id)])
        assert reader_check.main([]) == 0
    finally:
        del ANSWERS[8011]
    row = next(x for x in capsys.readouterr().out.splitlines() if x.split()[:1] == ["vllm"])
    assert f"{long_id} (server: {other})" in row and "<key>" not in row


def test_a_configured_host_is_scrubbed_only_as_an_address(world):
    """A configured host is replaced only as a whole token, and one with no dot only where it is written as an
    address (after // or @, or before a port): the word "gpu" in a sentence stays."""
    readers = [{"name": "box", "url": "http://gpu:8000/v1", "model": "m"},
               {"name": "lan", "url": "http://srv.example.net:9000/v1", "model": "m"}]
    assert vlm.scrub("the gpu is busy, gpus are hot, gpu-2 too", listed=readers) == "the gpu is busy, gpus are hot, gpu-2 too"
    assert vlm.scrub("connect to gpu:8000 failed", listed=readers) == "connect to <address> failed"
    assert vlm.scrub("see http://gpu/x and user@gpu", listed=readers) == "see <address> and user@<address>"
    assert vlm.scrub("srv.example.net refused; mysrv.example.network ok", listed=readers) == (
        "<address> refused; mysrv.example.network ok")


def test_a_config_that_cannot_be_read_is_said_plainly(world, capsys):
    """private/config.json that is no JSON, or whose "roles" is no object, or that is no object at all: one plain
    sentence naming what is wrong, no traceback, no path and nothing the file holds; the tool exits UNREADABLE and a
    run's start stops with the same sentence, before anything is asked."""
    import reader_check
    write, sent = world
    for text, said in (('{"readers": [{"name": "omlx", "url": "http://127.0.0.1:8001/v1", "model": "m"},]}',
                        "private/config.json is not valid JSON at line 1, column "),
                       (json.dumps({"readers": [local("omlx", 8001)], "roles": ["omlx"]}),
                        "private/config.json: \"roles\" is not an object giving each role a reader's name"),
                       (json.dumps({"readers": [local("omlx", 8001)], "roles": {"second": 3}}),
                        "private/config.json: \"roles\" is not an object giving each role a reader's name"),
                       (json.dumps([local("omlx", 8001)]),
                        "private/config.json is not in the shape the kit reads (AttributeError)")):
        camkit.CONFIG.write_text(text, encoding="utf-8")
        assert reader_check.main([]) == reader_check.UNREADABLE, text
        out = capsys.readouterr().out
        assert said in out and "Traceback" not in out and "127.0.0.1" not in out and str(camkit.CONFIG) not in out, out
        with pytest.raises(camkit.ConfigMissing) as stop:
            vlm.check_readers()
        assert str(stop.value).startswith(said) and str(camkit.CONFIG.parent) not in str(stop.value)
        assert "copy" not in out and "copy" not in str(stop.value)      # never: the file holds the person's settings
    assert sent == []


def test_a_fault_in_the_kit_is_never_blamed_on_the_config(world, monkeypatch, capsys):
    """A fault that is not in private/config.json (a bug in the verdict, Pillow missing, a KeyError in role(), the OCR
    engine finder failing) is said as itself: by the tool as "reader_check failed: <type>: <message>", scrubbed, with a
    status of its own; at a run's start raised as itself, never as an unreadable config (still before the link:
    kit/tests/test_scripts.py)."""
    import reader_check
    from camkit import ocr
    write, sent = world
    write([local("omlx", 8001)])

    def bug(*a, **k):
        raise TypeError("boom at http://127.0.0.1:9/v1")

    def no_pillow():
        raise ImportError("No module named 'PIL'")

    def finder_broke():
        raise RuntimeError("the OCR helper crashed")
    with monkeypatch.context() as m:
        m.setattr(vlm, "verdict", bug)
        assert reader_check.main([]) == reader_check.FAILED
        out = capsys.readouterr().out
        assert out.splitlines()[-1] == "reader_check failed: TypeError: boom at <address>" and "config.json" not in out
        with pytest.raises(TypeError, match="boom"):
            vlm.check_readers()
    with monkeypatch.context() as m:
        m.setattr(vlm, "check_picture", no_pillow)
        assert reader_check.main([]) == reader_check.FAILED
        assert capsys.readouterr().out.splitlines()[-1] == "reader_check failed: ImportError: No module named 'PIL'"
        with pytest.raises(ImportError):
            vlm.check_readers()
    with monkeypatch.context() as m:
        m.setattr(vlm, "role", lambda name: {}["second"])
        with pytest.raises(KeyError):
            vlm.check_readers()
    with monkeypatch.context() as m:
        m.setattr(ocr, "second", finder_broke)
        with pytest.raises(RuntimeError, match="the OCR helper crashed"):
            vlm.check_readers()
    assert sent == [] or ports(sent) == [8001] * len(sent)       # only the stub was ever asked


def test_the_server_named_model_is_shown_where_it_differs(world, capsys):
    import reader_check
    write, _ = world
    write([local("vllm", 8008, "Served-VL-8B"), local("omlx", 8008, "my-alias")])
    assert reader_check.main([]) == 0
    out = capsys.readouterr().out
    row = next(x for x in out.splitlines() if x.split()[:1] == ["omlx"])
    assert "my-alias (server: Served-VL-8B)" in row and "/Users" not in out
    row = next(x for x in out.splitlines() if x.split()[:1] == ["vllm"])
    assert "(server:" not in row


def test_ask_checks_keeps_no_late_answer(world, monkeypatch):
    """A reader that answers after the deadline changes nothing in the Checks already returned."""
    write, _ = world
    write([local("late", 8001)])
    release, written = threading.Event(), threading.Event()
    real = vlm.ask_check

    def slow(cfg, image, timeout, roles=()):
        release.wait(5)
        try:
            return real(cfg, image, timeout, roles)
        finally:
            written.set()
    monkeypatch.setattr(vlm, "ask_check", slow)
    monkeypatch.setattr(vlm, "CHECK_WAITS", (None,))
    monkeypatch.setattr(vlm, "CHECK_SLACK", 0.0)
    got = vlm.ask_checks([local("late", 8001)], b"png", timeout=0.2)
    assert got[0].error == "no answer within 0.2 s (timed out)" and not got[0].ok
    release.set()
    assert written.wait(5)
    assert got[0].error == "no answer within 0.2 s (timed out)" and not got[0].ok


# ---------------------------------------------------------------------------------------------- kit/tools/reader_check.py

def test_the_tool_prints_each_reader_and_exits_by_whether_a_run_would_start(world, capsys):
    import reader_check
    write, sent = world
    write([local("vllm", 8003, "big-model"), local("omlx", 8001, "small-model"), hosted("openai", 8006)])
    assert reader_check.main([]) == 0
    out = capsys.readouterr().out
    lines = out.splitlines()
    assert lines[0].startswith("reader check: each reader is asked to read 'MENU 42' off a small picture")
    row = next(x for x in lines if x.split()[:1] == ["omlx"])
    assert row.split()[1:5] == ["openai-compatible", "small-model", "third", "answered"] and "'MENU 42'" in row
    row = next(x for x in lines if x.split()[:1] == ["vllm"])
    assert "NO ANSWER after" in row and row.endswith("no answer within 25 s (timed out)")
    row = next(x for x in lines if x.split()[:1] == ["openai"])
    assert "openai-compatible, paid" in row and "not asked: a run never asks it" in row
    assert lines[-1] == "1 of 2 readers asked answered: a camera run would start; 'omlx' would stand in as the second reader."
    assert "127.0.0.1" not in out and "sk-test" not in out and ports(sent) == [8001, 8003]
    sent.clear()
    assert reader_check.main(["--all"]) == 0 and ports(sent) == [8001, 8003, 8006]
    capsys.readouterr()
    write([local("vllm", 8003), hosted("openai", 8006)])
    assert reader_check.main(["--local"]) == 1 and ports(sent) == [8003]
    out = capsys.readouterr().out
    assert "not asked: paid: not asked with --local" in out and "a camera run would stop before its link" in out


def test_the_tool_with_only_paid_readers_and_local_asks_none_and_says_so(world, capsys):
    import reader_check
    write, sent = world
    write([hosted("openai", 8006), {"name": "claude", "kind": "anthropic", "model": "claude-opus-5-5"}])
    assert reader_check.main(["--local"]) == reader_check.ONLY_PAID and sent == []
    assert ("only paid readers are listed ('openai', 'claude'): none is asked with --local. kit/tools/reader_check.py "
            "--all asks them, each question costing money.") in capsys.readouterr().out
    write([local("omlx", 8002), hosted("openai", 8006)], roles={"second": "openai", "third": "omlx"})
    assert reader_check.main(["--local"]) == 1
    assert ("no local reader answered, and the second reader, 'openai', is paid and not asked with --local: a camera "
            "run would start only if it answers") in capsys.readouterr().out


def test_the_tool_with_nothing_to_ask_or_a_malformed_entry_says_what_to_do(world, capsys):
    import reader_check
    write, sent = world
    write([])
    assert reader_check.main([]) == reader_check.NOTHING_TO_ASK
    assert "lists no reader: copy the ones you choose" in capsys.readouterr().out
    write([{"url": "http://127.0.0.1:8001/v1", "model": "m"}])
    assert reader_check.main([]) == reader_check.UNREADABLE
    out = capsys.readouterr().out
    assert "private/config.json: entry 1 of \"readers\" has no \"name\"" in out and "Traceback" not in out
    camkit.CONFIG.unlink()
    assert reader_check.main([]) == reader_check.NOTHING_TO_ASK
    assert "No private/config.json" in capsys.readouterr().out and sent == []
