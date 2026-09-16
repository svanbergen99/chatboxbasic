import http.client
import importlib
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DummyCaseyHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/health":
            return self.send_json({"ok": True})
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/chat":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length) or b"{}")
        message = str(data.get("message") or "")
        self.send_json({"reply": f"Casey testantwoord: {message}"})


class CaseyHandoffContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.casey_backend = ThreadingHTTPServer(("127.0.0.1", 0), DummyCaseyHandler)
        cls.casey_thread = threading.Thread(target=cls.casey_backend.serve_forever, daemon=True)
        cls.casey_thread.start()

        casey_port = cls.casey_backend.server_address[1]
        os.environ["CASEY_URL"] = f"http://127.0.0.1:{casey_port}/api/chat"
        os.environ["DEE_URL"] = ""
        os.environ["KCD_HANDOFF_SECRET"] = "casey-test-secret"
        os.environ["KCD_PUBLIC_ORIGIN"] = ""
        os.environ["KCD_COOKIE_SECURE"] = "0"
        os.environ["KCD_DEV_MODE"] = "0"
        os.environ["CHATBOX_ALLOWED_DEVICES"] = ""

        cls.gateway_module = importlib.import_module("server")
        cls.gateway = ThreadingHTTPServer(("127.0.0.1", 0), cls.gateway_module.Handler)
        cls.gateway_thread = threading.Thread(target=cls.gateway.serve_forever, daemon=True)
        cls.gateway_thread.start()
        cls.gateway_port = cls.gateway.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.gateway.shutdown()
        cls.gateway.server_close()
        cls.casey_backend.shutdown()
        cls.casey_backend.server_close()

    def request(self, method, path, body=None, headers=None):
        payload = None
        request_headers = dict(headers or {})
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
            request_headers["Content-Length"] = str(len(payload))

        connection = http.client.HTTPConnection("127.0.0.1", self.gateway_port, timeout=5)
        connection.request(method, path, body=payload, headers=request_headers)
        response = connection.getresponse()
        raw = response.read()
        result = {
            "status": response.status,
            "headers": {key.lower(): value for key, value in response.getheaders()},
            "body": raw,
        }
        connection.close()
        return result

    def json_body(self, response):
        return json.loads(response["body"].decode("utf-8"))

    def test_casey_handoff_end_to_end_and_dee_is_blocked(self):
        no_secret = self.request(
            "POST",
            "/api/handoff/issue",
            {"assistant": "casey", "message": "Wat is mijn planning?"},
        )
        self.assertEqual(no_secret["status"], 403)

        issue = self.request(
            "POST",
            "/api/handoff/issue",
            {"assistant": "casey", "message": "Wat is mijn planning?"},
            {"X-KCD-Handoff-Secret": "casey-test-secret"},
        )
        self.assertEqual(issue["status"], 200)
        issue_data = self.json_body(issue)
        self.assertEqual(issue_data["assistant"], "casey")
        self.assertTrue(issue_data["redirect"].startswith("/collega/casey?code="))
        handoff_url = issue_data["redirect"]

        exchange = self.request("GET", handoff_url)
        self.assertEqual(exchange["status"], 303)
        self.assertEqual(exchange["headers"].get("location"), "/collega/casey")
        set_cookie = exchange["headers"].get("set-cookie", "")
        self.assertIn("kcd_session=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Lax", set_cookie)
        cookie = set_cookie.split(";", 1)[0]

        replay = self.request("GET", handoff_url)
        self.assertEqual(replay["status"], 401)

        casey_page = self.request("GET", "/collega/casey", headers={"Cookie": cookie})
        self.assertEqual(casey_page["status"], 200)
        self.assertIn(b"Casey", casey_page["body"])

        dee_page = self.request("GET", "/collega/dee", headers={"Cookie": cookie})
        self.assertEqual(dee_page["status"], 403)

        status = self.request("GET", "/api/status", headers={"Cookie": cookie})
        self.assertEqual(status["status"], 200)
        status_data = self.json_body(status)
        self.assertEqual(status_data["session"]["role"], "casey")
        self.assertEqual(status_data["session"]["allowedChats"], ["3"])
        self.assertEqual(set(status_data["chatboxes"].keys()), {"3"})

        pending = self.request(
            "POST",
            "/api/session/pending-message",
            {},
            {"Cookie": cookie},
        )
        self.assertEqual(pending["status"], 200)
        self.assertEqual(self.json_body(pending)["message"], "Wat is mijn planning?")

        pending_again = self.request(
            "POST",
            "/api/session/pending-message",
            {},
            {"Cookie": cookie},
        )
        self.assertEqual(pending_again["status"], 200)
        self.assertEqual(self.json_body(pending_again)["message"], "")

        dee_chat = self.request(
            "POST",
            "/api/chat/4",
            {"message": "Dit mag niet naar Dee"},
            {"Cookie": cookie},
        )
        self.assertEqual(dee_chat["status"], 403)

        casey_chat = self.request(
            "POST",
            "/api/chat/3",
            {"message": "Hallo Casey"},
            {"Cookie": cookie},
        )
        self.assertEqual(casey_chat["status"], 200)
        casey_data = self.json_body(casey_chat)
        self.assertEqual(casey_data["chatId"], "3")
        self.assertEqual(casey_data["name"], "Casey")
        self.assertEqual(casey_data["reply"], "Casey testantwoord: Hallo Casey")


if __name__ == "__main__":
    unittest.main()
