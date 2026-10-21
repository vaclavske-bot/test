"""Prova login/ricerca contro un server OFF finto in locale (http, nessuna rete esterna)."""
import http.server, json, os, sys, tempfile, threading, urllib.parse
os.environ["PL_DB"] = tempfile.mktemp(suffix=".db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import import_off as I

class Fake(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        d = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        ok = d.get("user_id") == ["mario"] and d.get("password") == ["segreta"]
        self.send_response(200)
        if ok: self.send_header("Set-Cookie", "session=abc123; Path=/")
        self.end_headers(); self.wfile.write(b"ok")
    def do_GET(self):
        logged = "session=abc123" in (self.headers.get("Cookie") or "")
        self.send_response(200); self.end_headers()
        self.wfile.write(json.dumps({"products": [{"code": "1", "product_name": "P", "logged": logged}]}).encode())
    def log_message(self, *a): pass

srv = http.server.HTTPServer(("127.0.0.1", 0), Fake); threading.Thread(target=srv.serve_forever, daemon=True).start()
# il codice usa https: per il test sostituisco solo lo schema
import urllib.request
orig = urllib.request.Request
urllib.request.Request = lambda url, *a, **k: orig(url.replace("https://", "http://"), *a, **k)
host = f"127.0.0.1:{srv.server_port}"
assert I.login(host, "mario", "sbagliata") is False
I.HOST = host
assert I.fetch_page("conad", 1, 10)[0]["logged"] is False          # senza login
assert I.login(host, "mario", "segreta") is True
assert I.fetch_page("conad", 1, 10)[0]["logged"] is True           # cookie di sessione inviato
print("OK")
