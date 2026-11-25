"""TrueCFB reply bot: the conversation with the model, for either provider.

  chat(system, tools, provider, model) -> a Chat
  Chat.say(text)                       adds a user message
  Chat.step() -> [{"id", "name", "args"}] the lookups (or the reply) the model calls next
  Chat.answer([(id, text), ...])       gives the model what its calls returned
  Chat.provider, Chat.model, Chat.usage (one entry per call: tokens in, cached, out, seconds)

The model must call a tool on every turn (a lookup, or `reply` with its answer), so every turn is
structured and nothing it writes goes anywhere except through reply_agent.py's checks.

Provider, from the environment:
  REPLY_PROVIDER  grok or claude; when not set, grok if XAI_API_KEY is set, otherwise claude
  REPLY_MODEL     defaults: grok-4.7 (xAI), claude-sonnet-5-5 (Anthropic)
  XAI_API_KEY or ANTHROPIC_API_KEY
"""
import json
import os
import time

DEFAULT_MODEL = {"grok": "grok-4.7", "claude": "claude-sonnet-5-5"}
GROK_TRIES = 4
MAX_TOKENS = 4000


class GrokChat:
    """xAI's chat completions API (OpenAI-style tool calls)."""

    def __init__(self, model, system, tools):
        self.provider, self.model, self.usage = "grok", model, []
        self.messages = [{"role": "system", "content": system}]
        self.tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                         "parameters": t["parameters"]}} for t in tools]

    def say(self, text):
        self.messages.append({"role": "user", "content": text})

    def _post(self, body):
        import requests
        for attempt in range(GROK_TRIES):
            try:
                r = requests.post("https://api.x.ai/v1/chat/completions", timeout=180, json=body,
                                  headers={"Authorization": f"Bearer {os.environ['XAI_API_KEY']}"})
            except (requests.ConnectionError, requests.Timeout):
                if attempt == GROK_TRIES - 1:
                    raise
                time.sleep(2 ** (attempt + 1))
                continue
            # Slow down when xAI asks (429: the key allows 60 requests a minute) or has a passing error.
            if (r.status_code == 429 or r.status_code >= 500) and attempt < GROK_TRIES - 1:
                wait = r.headers.get("retry-after", "")
                time.sleep(min(float(wait) if wait.replace(".", "", 1).isdigit() else 2 ** (attempt + 2), 60))
                continue
            break
        if r.status_code != 200:
            raise RuntimeError(f"xAI API {r.status_code}: {r.text[:200]}")
        return r.json()

    def step(self):
        t0 = time.monotonic()
        j = self._post({"model": self.model, "messages": self.messages, "tools": self.tools,
                        "tool_choice": "required", "max_tokens": MAX_TOKENS})
        u = j.get("usage", {})
        self.usage.append({"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0),
                           "cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                           "seconds": round(time.monotonic() - t0, 1)})
        msg = j["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        self.messages.append({"role": "assistant", "content": msg.get("content") or "", **({"tool_calls": calls} if calls else {})})
        out = []
        for c in calls:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            out.append({"id": c["id"], "name": c["function"]["name"], "args": args if isinstance(args, dict) else {}})
        return out

    def answer(self, results):
        for cid, text in results:
            self.messages.append({"role": "tool", "tool_call_id": cid, "content": text})


class ClaudeChat:
    """Anthropic's Messages API."""

    def __init__(self, model, system, tools):
        import anthropic
        self.client = anthropic.Anthropic()
        self.provider, self.model, self.usage = "claude", model, []
        self.system = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        self.tools = [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools]
        self.messages = []

    def say(self, text):
        self.messages.append({"role": "user", "content": text})

    def step(self):
        t0 = time.monotonic()
        r = self.client.messages.create(model=self.model, max_tokens=MAX_TOKENS, system=self.system,
                                        messages=self.messages, tools=self.tools, tool_choice={"type": "any"})
        self.usage.append({"in": r.usage.input_tokens + (getattr(r.usage, "cache_read_input_tokens", 0) or 0),
                           "out": r.usage.output_tokens,
                           "cached": getattr(r.usage, "cache_read_input_tokens", 0) or 0,
                           "seconds": round(time.monotonic() - t0, 1)})
        if r.stop_reason == "refusal":
            raise RuntimeError("the model declined to answer")
        self.messages.append({"role": "assistant", "content": r.content})
        return [{"id": b.id, "name": b.name, "args": dict(b.input or {})} for b in r.content if b.type == "tool_use"]

    def answer(self, results):
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": cid, "content": text} for cid, text in results]})


PROVIDERS = {"grok": GrokChat, "claude": ClaudeChat}


def pick(provider=None, model=None):
    """(provider, model): what was asked for, else the environment, else Grok when its key is set."""
    provider = provider or os.environ.get("REPLY_PROVIDER") or ("grok" if os.environ.get("XAI_API_KEY") else "claude")
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r} (grok or claude)")
    return provider, model or os.environ.get("REPLY_MODEL") or DEFAULT_MODEL[provider]


def chat(system, tools, provider=None, model=None):
    provider, model = pick(provider, model)
    return PROVIDERS[provider](model, system, tools)
