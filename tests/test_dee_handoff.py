import http.client
import importlib
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DummyDeeHandler(BaseHTTPRequestHandler):
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
        if self.path == "/health":
            return self.send_json({"ok": True})
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/chat":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(length) or b"{}")
        message = str(data.get("message") or "")
        self.send_json({"reply": f"Dee testantwoord: {message}"})


class DeeHandoffContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dee_backend = ThreadingHTTPServer(("127.0.0.1", 0), DummyDeeHandler)
        cls.dee_thread = threading.Thread(target=cls.dee_backend.serve_forever, daemon=True)
        cls.dee_thread.start()

        dee_port = cls.dee_backend.server_address[1]
        os.environ["CASEY_URL"] = ""
        os.environ["DEE_URL"] = f"http://127.0.0.1:{dee_port}/api/chat"
        os.environ["KCD_HANDOFF_SECRET"] = "dee-test-secret"
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
        cls.dee_backend.shutdown()
        cls.dee_backend.server_close()

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

    def test_dee_handoff_end_to_end_and_casey_is_blocked(self):
        no_secret = self.request(
            "POST",
            "/api/handoff/issue",
            {"assistant": "dee", "message": "Wat moet ik vandaag regelen?"},
        )
        self.assertEqual(no_secret["status"], 403)

        issue = self.request(
            "POST",
            "/api/handoff/issue",
            {"assistant": "dee", "message": "Wat moet ik vandaag regelen?"},
            {"X-KCD-Handoff-Secret": "dee-test-secret"},
        )
        self.assertEqual(issue["status"], 200)
        issue_data = self.json_body(issue)
        self.assertEqual(issue_data["assistant"], "dee")
        self.assertTrue(issue_data["redirect"].startswith("/collega/dee?code="))
        handoff_url = issue_data["redirect"]

        exchange = self.request("GET", handoff_url)
        self.assertEqual(exchange["status"], 303)
        self.assertEqual(exchange["headers"].get("location"), "/collega/dee")
        set_cookie = exchange["headers"].get("set-cookie", "")
        self.assertIn("kcd_session=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertIn("SameSite=Lax", set_cookie)
        cookie = set_cookie.split(";", 1)[0]

        replay = self.request("GET", handoff_url)
        self.assertEqual(replay["status"], 401)

        dee_page = self.request("GET", "/collega/dee", headers={"Cookie": cookie})
        self.assertEqual(dee_page["status"], 200)
        self.assertIn(b"Dee", dee_page["body"])

        casey_page = self.request("GET", "/collega/casey", headers={"Cookie": cookie})
        self.assertEqual(casey_page["status"], 403)

        status = self.request("GET", "/api/status", headers={"Cookie": cookie})
        self.assertEqual(status["status"], 200)
        status_data = self.json_body(status)
        self.assertEqual(status_data["session"]["role"], "dee")
        self.assertEqual(status_data["session"]["allowedChats"], ["4"])
        self.assertEqual(set(status_data["chatboxes"].keys()), {"4"})
        self.assertTrue(status_data["chatboxes"]["4"]["online"])

        pending = self.request(
            "POST",
            "/api/session/pending-message",
            {},
            {"Cookie": cookie},
        )
        self.assertEqual(pending["status"], 200)
        self.assertEqual(self.json_body(pending)["message"], "Wat moet ik vandaag regelen?")

        pending_again = self.request(
            "POST",
            "/api/session/pending-message",
            {},
            {"Cookie": cookie},
        )
        self.assertEqual(pending_again["status"], 200)
        self.assertEqual(self.json_body(pending_again)["message"], "")

        casey_chat = self.request(
            "POST",
            "/api/chat/3",
            {"message": "Dit mag niet naar Casey"},
            {"Cookie": cookie},
        )
        self.assertEqual(casey_chat["status"], 403)

        dee_chat = self.request(
            "POST",
            "/api/chat/4",
            {"message": "Hallo Dee"},
            {"Cookie": cookie},
        )
        self.assertEqual(dee_chat["status"], 200)
        dee_data = self.json_body(dee_chat)
        self.assertEqual(dee_data["chatId"], "4")
        self.assertEqual(dee_data["name"], "Dee")
        self.assertEqual(dee_data["reply"], "Dee testantwoord: Hallo Dee")


if __name__ == "__main__":
    unittest.main()
