# -*- coding: utf-8 -*-
"""
Reaction Bot - Vercel version (Telegram webhook)
- هیچ پرۆسێسێکی هەمیشە-کار نییە؛ Telegram خۆی نامە نوێیەکان دەنێرێت بۆ ئەم فەنکشنە
- ڕێکخستنەکان و ئامار لە Upstash Redis پاشەکەوت دەکرێن (Vercel Storage)
- API ی ئەدمین هاوشێوەی server.py: /api/status /api/logs /api/config /api/start /api/stop
ENV: BOT_TOKEN, ADMIN_KEY  (+ KV_REST_API_URL / KV_REST_API_TOKEN لە Redis ەوە بە خۆکاری)
"""
import hashlib
import hmac
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default


TOKEN = (os.environ.get("BOT_TOKEN") or "").strip()
ADMIN_KEY = (os.environ.get("ADMIN_KEY") or "").strip()
TG_API = (os.environ.get("TELEGRAM_API") or "https://api.telegram.org").rstrip("/")
TZ_HOURS = _int("TZ_OFFSET_HOURS", 3)  # کاتی کوردستان/عێراق

EMOJIS = [
    "👍", "👎", "❤️", "🔥", "🥰", "👏", "😁", "🤔", "🤯", "😱", "😢", "🎉", "🤩", "🙏", "👌",
    "🕊", "🤡", "🥱", "🥴", "😍", "🐳", "❤️‍🔥", "🌚", "🌭", "💯", "🤣", "⚡", "🍌", "🏆", "💔",
    "🤨", "😐", "🍓", "🍾", "💋", "😈", "😴", "😭", "🤓", "👻", "👨‍💻", "👀", "🎃", "🙈", "😇",
    "😨", "🤝", "✍", "🤗", "🫡", "🎅", "🎄", "☃", "💅", "🤪", "🗿", "🆒", "💘", "🙉", "🦄",
    "😘", "💊", "🙊", "😎", "👾", "😡",
]

SERVICE_KEYS = (
    "new_chat_members", "left_chat_member", "new_chat_title", "new_chat_photo",
    "delete_chat_photo", "group_chat_created", "pinned_message",
    "message_auto_delete_timer_changed", "forum_topic_created",
    "forum_topic_closed", "forum_topic_reopened",
)

DEFAULTS = {
    "enabled": True,
    "emoji_index": _int("EMOJI_INDEX", 0),
    "delay_ms": _int("DELAY_MS", 200),
    "skip_pct": _int("SKIP_PCT", 5),
}


# ───────────── Redis (Upstash REST) ─────────────

def _redis_conf():
    url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL") or ""
    tok = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN") or ""
    return url.rstrip("/"), tok


def has_redis():
    u, t = _redis_conf()
    return bool(u and t)


def _redis_post(path, payload):
    url, tok = _redis_conf()
    if not url or not tok:
        raise RuntimeError("no redis")
    req = urllib.request.Request(
        url + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.loads(r.read().decode("utf-8"))


def rcmd(*args):
    return _redis_post("", [str(a) for a in args]).get("result")


def rpipe(cmds):
    out = _redis_post("/pipeline", [[str(a) for a in c] for c in cmds])
    return [x.get("result") for x in out]


# ───────────── helpers ─────────────

def clamp(v, lo, hi, default):
    try:
        v = int(v)
    except Exception:
        return default
    return max(lo, min(hi, v))


def now_str():
    return (datetime.now(timezone.utc) + timedelta(hours=TZ_HOURS)).strftime("%H:%M:%S")


def webhook_secret():
    return hashlib.sha256(("%s:%s" % (ADMIN_KEY, TOKEN)).encode("utf-8")).hexdigest()[:48]


def load_config():
    cfg = dict(DEFAULTS)
    try:
        raw = rcmd("GET", "rb:config")
        if raw:
            cfg.update(json.loads(raw))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    rcmd("SET", "rb:config", json.dumps(cfg))


def record(stat=None, line=None):
    cmds = []
    if stat:
        cmds.append(["HINCRBY", "rb:stats", stat, 1])
    if line:
        cmds.append(["LPUSH", "rb:logs", "%s  %s" % (now_str(), line)])
        cmds.append(["LTRIM", "rb:logs", 0, 99])
    if cmds:
        try:
            rpipe(cmds)
        except Exception:
            pass


def tg(method, payload=None, timeout=10):
    req = urllib.request.Request(
        "%s/bot%s/%s" % (TG_API, TOKEN, method),
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "error_code": e.code, "description": str(e)}


def pick_emoji(cfg):
    idx = cfg.get("emoji_index", 0)
    if idx <= 0 or idx > len(EMOJIS):
        return random.choice(EMOJIS)
    return EMOJIS[idx - 1]


def react(chat_id, message_id, emoji):
    return tg("setMessageReaction", {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": emoji}],
    })


def status_payload():
    cfg = load_config()
    stats, since, bot = {}, None, ""
    try:
        res = rpipe([["HGETALL", "rb:stats"], ["GET", "rb:since"], ["GET", "rb:bot"]])
        flat = res[0] or []
        stats = {flat[i]: int(flat[i + 1]) for i in range(0, len(flat) - 1, 2)}
        since = float(res[1]) if res[1] else None
        bot = res[2] or ""
    except Exception:
        pass
    uptime = int(time.time() - since) if (since and cfg["enabled"]) else 0
    return {
        "running": bool(cfg["enabled"]),
        "bot": bot,
        "reacted": stats.get("reacted", 0),
        "skipped": stats.get("skipped", 0),
        "errors": stats.get("errors", 0),
        "uptime": uptime,
        "queue": 0,
        "storage": has_redis(),
        "config": {
            "emoji_index": cfg["emoji_index"],
            "delay_ms": cfg["delay_ms"],
            "skip_pct": cfg["skip_pct"],
        },
    }


def process_update(u):
    m = u.get("message") or u.get("channel_post")
    if not m or any(k in m for k in SERVICE_KEYS):
        return
    cfg = load_config()
    if not cfg.get("enabled", True):
        return
    if random.random() * 100 < clamp(cfg.get("skip_pct", 5), 0, 95, 5):
        record(stat="skipped")
        return

    time.sleep(clamp(cfg.get("delay_ms", 200), 0, 5000, 200) / 1000.0)

    chat = m.get("chat", {})
    cid, mid = chat.get("id"), m.get("message_id")
    title = chat.get("title") or chat.get("first_name") or "چات"
    emoji = pick_emoji(cfg)

    r = react(cid, mid, emoji)
    if not r.get("ok") and r.get("error_code") == 400 and cfg.get("emoji_index", 0) <= 0:
        emoji = pick_emoji(cfg)
        r = react(cid, mid, emoji)
    if not r.get("ok") and r.get("error_code") == 429:
        wait = 2
        try:
            wait = int(r.get("parameters", {}).get("retry_after", 2))
        except Exception:
            pass
        time.sleep(min(wait, 4))
        r = react(cid, mid, emoji)

    if r.get("ok"):
        record(stat="reacted", line="%s  %s" % (emoji, title))
    else:
        record(stat="errors", line="ڕیاکشن سەرنەکەوت لە %s: %s" % (title, r.get("description", "?")))


# ───────────── HTTP handler ─────────────

class handler(BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass

    def _send(self, code, obj, ctype="application/json; charset=utf-8"):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _route(self):
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        op = (q.get("op") or [""])[0]
        if not op:
            op = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        return op, q

    def _authorized(self, q):
        key = self.headers.get("X-Admin-Key") or (q.get("key") or [""])[0]
        return bool(ADMIN_KEY) and hmac.compare_digest(key.encode("utf-8"), ADMIN_KEY.encode("utf-8"))

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            n = 0
        return self.rfile.read(n) if 0 < n <= 1048576 else b""

    def do_GET(self):
        op, q = self._route()
        if op == "health":
            return self._send(200, b"ok", "text/plain; charset=utf-8")
        if op in ("", "index", "root"):
            return self._send(200, {"name": "reaction-bot-vercel", "ok": True})
        if not TOKEN or not ADMIN_KEY:
            return self._send(500, {"error": "BOT_TOKEN یان ADMIN_KEY دانەنراوە"})
        if not self._authorized(q):
            return self._send(401, {"error": "unauthorized"})

        if op == "setup":
            return self._setup()
        if op == "status":
            return self._send(200, status_payload())
        if op == "logs":
            n = clamp((q.get("n") or ["60"])[0], 1, 100, 60)
            try:
                lines = rcmd("LRANGE", "rb:logs", 0, n - 1) or []
            except Exception:
                lines = []
            return self._send(200, {"logs": lines})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        op, q = self._route()
        if not TOKEN or not ADMIN_KEY:
            return self._send(500, {"error": "BOT_TOKEN یان ADMIN_KEY دانەنراوە"})

        if op == "webhook":
            sec = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not hmac.compare_digest(sec.encode("utf-8"), webhook_secret().encode("utf-8")):
                return self._send(401, {"error": "bad secret"})
            try:
                process_update(json.loads(self._body().decode("utf-8") or "{}"))
            except Exception as e:
                record(stat="errors", line="هەڵە: %s" % type(e).__name__)
            return self._send(200, {"ok": True})  # هەمیشە 200، تا تێلیگرام دووبارە نەنێرێت

        if not self._authorized(q):
            return self._send(401, {"error": "unauthorized"})
        if not has_redis():
            return self._send(503, {"error": "Redis پەیوەست نەکراوە (Vercel > Storage)"})

        try:
            if op == "config":
                try:
                    data = json.loads(self._body().decode("utf-8") or "{}")
                except Exception:
                    return self._send(400, {"error": "bad json"})
                cfg = load_config()
                if "emoji_index" in data:
                    cfg["emoji_index"] = clamp(data["emoji_index"], 0, len(EMOJIS), 0)
                if "delay_ms" in data:
                    cfg["delay_ms"] = clamp(data["delay_ms"], 0, 5000, 200)
                if "skip_pct" in data:
                    cfg["skip_pct"] = clamp(data["skip_pct"], 0, 95, 5)
                if "enabled" in data:
                    cfg["enabled"] = bool(data["enabled"])
                save_config(cfg)
                return self._send(200, status_payload())
            if op in ("start", "stop"):
                cfg = load_config()
                cfg["enabled"] = (op == "start")
                save_config(cfg)
                if op == "start":
                    rcmd("SET", "rb:since", int(time.time()))
                record(line="بەکارهێنەر دەستی پێکرد" if op == "start" else "بەکارهێنەر وەستاندی")
                return self._send(200, status_payload())
        except Exception as e:
            return self._send(500, {"error": type(e).__name__})
        return self._send(404, {"error": "not found"})

    def _setup(self):
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host") or ""
        url = "https://%s/api/webhook" % host
        me = tg("getMe", {})
        if not me.get("ok"):
            return self._send(200, {"ok": False, "step": "getMe", "error": me.get("description", "تۆکێن هەڵەیە")})
        username = me["result"].get("username", "")
        r = tg("setWebhook", {
            "url": url,
            "secret_token": webhook_secret(),
            "allowed_updates": ["message", "channel_post"],
            "drop_pending_updates": True,
            "max_connections": 100,
        })
        if has_redis():
            try:
                rpipe([["SET", "rb:bot", username], ["SET", "rb:since", int(time.time())]])
            except Exception:
                pass
            record(line="Webhook دانرا بۆ @%s" % username)
        return self._send(200, {
            "ok": bool(r.get("ok")),
            "bot": username,
            "webhook_url": url,
            "storage": has_redis(),
            "telegram": r.get("description", ""),
            "note": "" if has_redis() else "Redis پەیوەست نەکراوە: ئەپەکە نایتوانێت ڕێکخستنەکان بگۆڕێت",
        })
