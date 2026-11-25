"""Thin client for the local Ollama server: JSON-schema constrained chat with optional images, retries on
schema failures, and explicit unloading so big models never fight the image generator for memory."""
import json
import time
import urllib.error
import urllib.request

from . import config


def _post(path, body, timeout=1800):
    req = urllib.request.Request(config.OLLAMA + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def chat_json(model, prompt, schema, images=(), system=None, temperature=0.2, retries=2, num_ctx=16384,
              think=False, timeout=600, log=None, num_predict=3000):
    """Returns (parsed_json, seconds). `schema` is a JSON schema passed to Ollama's `format`, so the model
    decodes valid JSON of that shape; we still validate required keys and retry if they are missing."""
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt, **({"images": list(images)} if images else {})})
    body = {"model": model, "messages": msgs, "stream": False, "format": schema,
            "options": {"temperature": temperature, "num_ctx": num_ctx, "num_predict": num_predict}}
    if "gpt-oss" in model:
        body["think"] = think if isinstance(think, str) else "low"
    elif model in config.THINK_OVERRIDE and not think:
        body["think"] = config.THINK_OVERRIDE[model]
    else:
        body["think"] = bool(think)
    if model in _NO_FORMAT:
        _schema_in_prompt(body, schema)
    last = None
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            try:
                res = _post("/api/chat", body, timeout)
            except urllib.error.HTTPError as e:
                if e.code != 501 or "format" not in body:
                    raise
                _NO_FORMAT.add(model)          # model has no constrained decoding: put the schema in the prompt
                _schema_in_prompt(body, schema)
                res = _post("/api/chat", body, timeout)
            txt = res["message"]["content"]
            out = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
            missing = [k for k in schema.get("required", []) if k not in out]
            if missing:
                raise ValueError("missing keys %s in: %s" % (missing, txt[:300].replace("\n", " ")))
            return out, time.time() - t0
        except (ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as e:
            last = e
            if log:
                log("  %s attempt %d failed: %s" % (model, attempt + 1, str(e)[:200]))
            body["options"]["temperature"] = min(0.7, temperature + 0.2 * (attempt + 1))
    raise RuntimeError("%s gave no valid JSON after %d attempts: %s" % (model, retries + 1, last))


_NO_FORMAT = set()


def _schema_in_prompt(body, schema):
    body.pop("format", None)
    msg = body["messages"][-1]
    if "OUTPUT FORMAT" not in msg["content"]:
        enums = {}
        _collect_enums(schema, enums)
        msg["content"] += ("\n\nOUTPUT FORMAT: reply with ONLY one JSON object (no prose, no code fences) with exactly "
                           "these keys, filled in with your answer:\n" + json.dumps(_example(schema)) +
                           ("\nAllowed values: " + json.dumps(enums) if enums else ""))


def _example(s):
    t = s.get("type")
    if t == "object":
        return {k: _example(v) for k, v in s.get("properties", {}).items()}
    if t == "array":
        return [_example(s.get("items", {}))]
    if "enum" in s:
        return s["enum"][0]
    return {"string": "...", "integer": 0, "number": 0.0, "boolean": False}.get(t, "...")


def _collect_enums(s, out, name=None):
    if "enum" in s and name:
        out[name] = s["enum"]
    for k, v in s.get("properties", {}).items():
        _collect_enums(v, out, k)
    if "items" in s:
        _collect_enums(s["items"], out, name)


def chat_text(model, prompt, system=None, temperature=0.2, num_ctx=32768, think="medium", timeout=1800):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": model, "messages": msgs, "stream": False,
            "options": {"temperature": temperature, "num_ctx": num_ctx}}
    body["think"] = think if "gpt-oss" in model else False
    t0 = time.time()
    res = _post("/api/chat", body, timeout)
    return res["message"]["content"], time.time() - t0


def unload(*models):
    for m in models:
        try:
            _post("/api/generate", {"model": m, "keep_alive": 0}, 120)
        except Exception:
            pass


def unload_all():
    try:
        with urllib.request.urlopen(config.OLLAMA + "/api/ps", timeout=10) as r:
            running = [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        running = []
    unload(*running)
    return running


def loaded():
    with urllib.request.urlopen(config.OLLAMA + "/api/ps", timeout=10) as r:
        return json.load(r).get("models", [])


def str_schema(**props):
    """Small helper to build object schemas: str_schema(a="string", b=["string"], c={...})."""
    def conv(v):
        if isinstance(v, dict):
            return v
        if isinstance(v, list):
            return {"type": "array", "items": conv(v[0])}
        return {"type": v}
    return {"type": "object", "properties": {k: conv(v) for k, v in props.items()}, "required": list(props)}
