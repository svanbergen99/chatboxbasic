from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import secrets
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("CHATBOX_HOST", "127.0.0.1")
PORT = int(os.environ.get("CHATBOX_PORT", "8080"))

AI_CORE_URL = os.environ.get("AI_CORE_URL", os.environ.get("AERO_URL", "http://127.0.0.1:8091/api/chat"))
DIVA_URL = os.environ.get("DIVA_URL", "http://127.0.0.1:8090/api/chat")
CASEY_URL = os.environ.get("CASEY_URL", "").strip()
DEE_URL = os.environ.get("DEE_URL", "").strip()

DEV_MODE = os.environ.get("KCD_DEV_MODE", "0").strip() == "1"
COOKIE_SECURE = os.environ.get("KCD_COOKIE_SECURE", "0").strip() == "1"
SESSION_TTL = int(os.environ.get("KCD_SESSION_TTL", str(8 * 60 * 60)))
SESSION_COOKIE = "kcd_session"

ROLE_CHATS = {
    "beheer": {"1", "2"},
    "casey": {"3"},
    "dee": {"4"},
}

PAGE_ROUTES = {
    "/beheer": {"file": "beheer.html", "role": "beheer"},
    "/beheer/": {"file": "beheer.html", "role": "beheer"},
    "/collega/casey": {"file": "casey.html", "role": "casey"},
    "/collega/casey/": {"file": "casey.html", "role": "casey"},
    "/collega/dee": {"file": "dee.html", "role": "dee"},
    "/collega/dee/": {"file": "dee.html", "role": "dee"},
}

ROLE_HOME = {
    "beheer": "/beheer",
    "casey": "/collega/casey",
    "dee": "/collega/dee",
}

CHATBOXES = {
    "/api/chat/1": {"id": "1", "name": "Aero", "backend": "Aero", "url": AI_CORE_URL},
    "/api/chat/2": {"id": "2", "name": "Diva", "backend": "Diva", "url": DIVA_URL},
    "/api/chat/3": {"id": "3", "name": "Casey", "backend": "Casey", "url": CASEY_URL},
    "/api/chat/4": {"id": "4", "name": "Dee", "backend": "Dee", "url": DEE_URL},
}

ALLOWED_DEVICE_IDS = {
    item.strip() for item in os.environ.get("CHATBOX_ALLOWED_DEVICES", "").split(",") if item.strip()
}

SESSIONS = {}
SESSIONS_LOCK = threading.Lock()


def call_agent(url: str, message: str) -> dict:
    if not url:
        raise RuntimeError("Backend is nog niet geconfigureerd.")
    payload = json.dumps({"message": message}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def agent_online(chat_url: str) -> bool:
    if not chat_url:
        return False
    health_url = chat_url.rsplit("/api/chat", 1)[0] + "/api/health"
    try:
        with urllib.request.urlopen(health_url, timeout=2) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def new_session(role: str) -> tuple[str, dict]:
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    session = {
        "role": role,
        "allowedChats": sorted(ROLE_CHATS[role]),
        "createdAt": now,
        "expiresAt": now + SESSION_TTL,
    }
    with SESSIONS_LOCK:
        SESSIONS[token] = session
    return token, session


def lookup_session(token: str):
    if not token:
        return None
    now = int(time.time())
    with SESSIONS_LOCK:
        session = SESSIONS.get(token)
        if not session:
            return None
        if session["expiresAt"] <= now:
            SESSIONS.pop(token, None)
            return None
        return dict(session)


def delete_session(token: str):
    if not token:
        return
    with SESSIONS_LOCK:
        SESSIONS.pop(token, None)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_json(self, data, status=200, extra_headers=None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for name, value in extra_headers:
                self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location, status=302, extra_headers=None):
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for name, value in extra_headers:
                self.send_header(name, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def session_cookie_header(self, token, max_age=SESSION_TTL):
        parts = [
            f"{SESSION_COOKIE}={token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Lax",
            f"Max-Age={max_age}",
        ]
        if COOKIE_SECURE:
            parts.append("Secure")
        return "; ".join(parts)

    def cookie_value(self, name):
        raw = self.headers.get("Cookie") or ""
        cookie = SimpleCookie()
        try:
            cookie.load(raw)
        except Exception:
            return ""
        morsel = cookie.get(name)
        return morsel.value if morsel else ""

    def current_session(self):
        return lookup_session(self.cookie_value(SESSION_COOKIE))

    def device_id(self):
        return (self.headers.get("X-Device-ID") or "").strip()

    def device_allowed(self):
        return not ALLOWED_DEVICE_IDS or self.device_id() in ALLOWED_DEVICE_IDS

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length) or b"{}")

    def require_session(self):
        session = self.current_session()
        if not session:
            self.send_json({"error": "Geen geldige sessie."}, 401)
            return None
        return session

    def do_GET(self):
        request_path = urlsplit(self.path).path

        if request_path == "/":
            session = self.current_session()
            return self.redirect(ROLE_HOME.get(session["role"], "/beheer") if session else "/beheer")

        if request_path == "/api/health":
            return self.send_json({"ok": True})

        if request_path == "/api/session":
            session = self.current_session()
            if not session:
                return self.send_json({"authenticated": False}, 401)
            return self.send_json({"authenticated": True, **session})

        if request_path == "/api/device":
            return self.send_json({
                "deviceId": self.device_id(),
                "securityEnabled": bool(ALLOWED_DEVICE_IDS),
                "allowed": self.device_allowed(),
            })

        if request_path == "/api/status":
            session = self.require_session()
            if not session:
                return
            allowed = set(session["allowedChats"])
            return self.send_json({
                "session": {"role": session["role"], "allowedChats": session["allowedChats"]},
                "chatboxes": {
                    chatbox["id"]: {
                        "name": chatbox["name"],
                        "backend": chatbox["backend"],
                        "configured": bool(chatbox["url"]),
                        "online": agent_online(chatbox["url"]),
                    }
                    for chatbox in CHATBOXES.values()
                    if chatbox["id"] in allowed
                },
                "deviceSecurity": bool(ALLOWED_DEVICE_IDS),
                "deviceAllowed": self.device_allowed(),
            })

        route = PAGE_ROUTES.get(request_path)
        if route:
            session = self.current_session()
            if not session:
                return self.send_error(401, "Geen geldige sessie")
            if session["role"] != route["role"]:
                return self.send_error(403, "Geen toegang tot deze pagina")
            path = ROOT / route["file"]
        else:
            path = ROOT / request_path.lstrip("/")

        resolved = path.resolve()
        if not path.is_file() or (ROOT not in resolved.parents and resolved != ROOT):
            return self.send_error(404)

        data = path.read_bytes()
        content_type = "text/html; charset=utf-8"
        if path.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"
        elif path.suffix == ".css":
            content_type = "text/css; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        request_path = urlsplit(self.path).path

        if request_path == "/api/dev/session":
            if not DEV_MODE:
                return self.send_error(404)
            try:
                data = self.read_json()
                role = str(data.get("role") or "").strip().lower()
                if role not in ROLE_CHATS:
                    return self.send_json({"error": "Onbekende development-rol."}, 400)
                old_token = self.cookie_value(SESSION_COOKIE)
                delete_session(old_token)
                token, session = new_session(role)
                return self.send_json(
                    {
                        "ok": True,
                        "role": role,
                        "allowedChats": session["allowedChats"],
                        "redirect": ROLE_HOME[role],
                    },
                    extra_headers=[("Set-Cookie", self.session_cookie_header(token))],
                )
            except Exception as exc:
                return self.send_json({"error": str(exc)}, 400)

        if request_path == "/api/session/logout":
            token = self.cookie_value(SESSION_COOKIE)
            delete_session(token)
            return self.send_json(
                {"ok": True},
                extra_headers=[("Set-Cookie", self.session_cookie_header("", max_age=0))],
            )

        chatbox = CHATBOXES.get(request_path)
        if not chatbox:
            return self.send_error(404)

        session = self.require_session()
        if not session:
            return

        if chatbox["id"] not in set(session["allowedChats"]):
            return self.send_json({"error": "Deze sessie heeft geen toegang tot deze chatbox."}, 403)

        if not self.device_allowed():
            return self.send_json({"error": "Dit apparaat is niet goedgekeurd."}, 403)

        if not chatbox["url"]:
            return self.send_json({"error": f'{chatbox["name"]} is nog niet gekoppeld aan een backend.'}, 503)

        try:
            data = self.read_json()
            message = str(data.get("message") or "").strip()
            if not message:
                return self.send_json({"error": "Leeg bericht."}, 400)

            result = call_agent(chatbox["url"], message)
            reply = result.get("reply") or result.get("error") or "Geen antwoord ontvangen."
            return self.send_json({
                "reply": reply,
                "chatId": chatbox["id"],
                "name": chatbox["name"],
                "backend": chatbox["backend"],
            })
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)


if __name__ == "__main__":
    print(f"KCD Chatbox: http://{HOST}:{PORT}")
    print("Pages: /beheer, /collega/casey, /collega/dee")
    print("Session rights: beheer=1+2, casey=3, dee=4")
    print(f"Development session endpoint: {'ON' if DEV_MODE else 'OFF'}")
    if ALLOWED_DEVICE_IDS:
        print(f"Device security: ON ({len(ALLOWED_DEVICE_IDS)} approved)")
    else:
        print("Device security: prepared, allowlist not configured")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
