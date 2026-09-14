from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import os
import urllib.request

ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("CHATBOX_HOST", "127.0.0.1")
PORT = int(os.environ.get("CHATBOX_PORT", "8080"))

# AI CORE ADAPTER
# Nu gekoppeld aan Aero (de huidige lokale chat-core).
# Later hoef je alleen AI_CORE_URL te vervangen door de URL van je eigen AI core.
AI_CORE_URL = os.environ.get("AI_CORE_URL", os.environ.get("AERO_URL", "http://127.0.0.1:8091/api/chat"))
DIVA_URL = os.environ.get("DIVA_URL", "http://127.0.0.1:8090/api/chat")


def call_agent(url: str, message: str) -> dict:
    payload = json.dumps({"message": message}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(response.read().decode("utf-8"))


def agent_online(chat_url: str) -> bool:
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

    def do_GET(self):
        if self.path == "/api/health":
            return self.send_json({"ok": True})
        if self.path == "/api/status":
            return self.send_json({"Aero": agent_online(AI_CORE_URL), "Diva": agent_online(DIVA_URL)})
        if self.path == "/":
            path = ROOT / "index.html"
        else:
            path = ROOT / self.path.lstrip("/")
        if not path.is_file() or ROOT not in path.resolve().parents and path.resolve() != ROOT:
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
        if self.path != "/api/chat":
            return self.send_error(404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length) or b"{}")
            message = str(data.get("message") or "").strip()
            if not message:
                return self.send_json({"error": "Leeg bericht."}, 400)
            is_diva = message.lower().startswith("diva:") or message.lower().startswith("diva ")
            url = DIVA_URL if is_diva else AI_CORE_URL
            result = call_agent(url, message)
            reply = result.get("reply") or result.get("error") or "Geen antwoord ontvangen."
            return self.send_json({"reply": reply, "agent": "Diva" if is_diva else "Aero"})
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)


if __name__ == "__main__":
    print(f"ChatBox Basic: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
