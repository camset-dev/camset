"""Claude as a vision reader, through the Anthropic Messages API, beside the OpenAI-compatible
servers in vlm.py (vLLM, omlx).

A private/config.json "readers" entry:

    {"name": "claude", "kind": "anthropic", "model": "claude-opus-5-5", "parallel": 4, "effort": "medium"}

Credentials are resolved by the SDK from the environment (ANTHROPIC_API_KEY, or an `ant auth login`
profile); the kit never reads, writes or stores a key. Same contract as vlm.Reader: ask(image,
prompt) returns the JSON object in the answer, cached by image + prompt + model, so a frame is paid
for once. A refused request is not cached, and comes back as {"_error": ...}, as a failed server
call does.

The request opts into server-side fallbacks ("default": the API re-runs a declined request on the
model Anthropic recommends for that refusal's category). Thinking is left on, as Claude Opus 5.5
requires; effort sets how hard it reads (default "medium", the model's own default).
"""
import base64
import threading

import anthropic

from .vlm import cache_key, cached, keep, parse_json

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeReader:
    def __init__(self, name, model="claude-opus-5-5", parallel=4, timeout=120, effort="medium", kind="anthropic",
                 url=None):
        del kind, url                                   # the config's own fields, not the SDK's
        self.name, self.model, self.effort = name, model, effort
        self.slots = threading.Semaphore(parallel)
        self.client = anthropic.Anthropic(timeout=timeout)

    def ask(self, image: bytes, prompt: str) -> dict:
        """The answer, from the cache when this model has answered this question about this picture, else asked
        (answer) and kept, unless refused."""
        key = cache_key(image, prompt, self.model)
        answer = cached(key)
        if answer is not None:
            return answer
        answer = self.answer(image, prompt)
        return answer if "_error" in answer else keep(key, answer)

    def answer(self, image: bytes, prompt: str, waits=None) -> dict:
        """The answer asked now, nothing looked up or kept (ask keeps it; camkit.vlm's start check asks this way). waits
        is vlm.Reader's, unused here: the SDK retries a busy service by itself."""
        del waits
        with self.slots:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                output_config={"effort": self.effort},
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": base64.standard_b64encode(image).decode("utf-8")}},
                    {"type": "text", "text": prompt}]}],
            )
        self.served = getattr(response, "model", None)          # the model that answered (a fallback's, after one)
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            return {"_error": f"refused ({category})"}
        text = "".join(block.text for block in response.content if block.type == "text")
        return parse_json(text)
