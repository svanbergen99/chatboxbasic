from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import urllib.request

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("CHATBOX_HOST", "127.0.0.1")
PORT = int(os.environ.get("CHATBOX_PORT", "8080"))

AI_CORE_URL = os.environ.get("AI_CORE_URL", os.environ.get("AERO_URL", "http://127.0.0.1:8091/api/chat"))
DIVA_URL = os.environ.get("DIVA_URL", "http://127.0.0.1:8090/api/chat")
CASEY_URL = os.environ.get("CASEY_URL", "").strip()
DEE_URL = os.environ.get("DEE_URL", "").strip()

PAGE_ROUTES = {
    "/beheer": "beheer.html",
    "/beheer/": "beheer.html",
    "/collega/casey": "casey.html",
    "/collega/casey/": "casey.html",
    "/collega/dee": "dee.html",
    "/collega/dee/": "dee.html",
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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location, status=302):
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def device_id(self):
        return (self.headers.get("X-Device-ID") or "").strip()

    def device_allowed(self):
        return not ALLOWED_DEVICE_IDS or self.device_id() in ALLOWED_DEVICE_IDS

    def do_GET(self):
        request_path = urlsplit(self.path).path

        if request_path == "/":
            return self.redirect("/beheer")

        if request_path == "/api/health":
            return self.send_json({"ok": True})

        if request_path == "/api/device":
            return self.send_json({
                "deviceId": self.device_id(),
                "securityEnabled": bool(ALLOWED_DEVICE_IDS),
                "allowed": self.device_allowed(),
            })

        if request_path == "/api/status":
            return self.send_json({
                "chatboxes": {
                    chatbox["id"]: {
                        "name": chatbox["name"],
                        "backend": chatbox["backend"],
                        "configured": bool(chatbox["url"]),
                        "online": agent_online(chatbox["url"]),
                    }
                    for chatbox in CHATBOXES.values()
                },
                "deviceSecurity": bool(ALLOWED_DEVICE_IDS),
                "deviceAllowed": self.device_allowed(),
            })

        routed_file = PAGE_ROUTES.get(request_path)
        path = ROOT / routed_file if routed_file else ROOT / request_path.lstrip("/")

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
        chatbox = CHATBOXES.get(request_path)
        if not chatbox:
            return self.send_error(404)

        if not self.device_allowed():
            return self.send_json({"error": "Dit apparaat is niet goedgekeurd."}, 403)

        if not chatbox["url"]:
            return self.send_json({"error": f'{chatbox["name"]} is nog niet gekoppeld aan een backend.'}, 503)

        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
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
    print("Chats: 1 Aero, 2 Diva, 3 Casey, 4 Dee")
    if ALLOWED_DEVICE_IDS:
        print(f"Device security: ON ({len(ALLOWED_DEVICE_IDS)} approved)")
    else:
        print("Device security: prepared, allowlist not configured")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
