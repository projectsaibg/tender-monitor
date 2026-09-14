"""Bundled mock tender portal for testing Tender Monitor end-to-end.

Run:   python tools/serve_mock.py
Serves a fake e-procurement listing at  http://127.0.0.1:8899/tenders

To try change/new detection:
  1. Add a portal in the dashboard with URL http://127.0.0.1:8899/tenders
     (set Delay=0). To scan localhost you must allow private hosts:
     set TENDER_MONITOR_ALLOW_PRIVATE_HOSTS=1 before starting the app.
  2. Scan once (creates a baseline), then open http://127.0.0.1:8899/switch
     to change/add tenders, and scan again to see UPDATED and NEW tenders.
"""
import http.server
import socketserver
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tests import mock_data

PORT = 8899
STATE = {"version": 1}


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, body, content_type="text/html; charset=utf-8", code=200):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/switch":
            STATE["version"] = 2 if STATE["version"] == 1 else 1
            self._send("<p>Now serving version %d. Re-scan the portal.</p>"
                       "<p><a href='/tenders'>View listing</a></p>" % STATE["version"])
            return
        if path.endswith(".pdf") or path.startswith("/docs"):
            self._send(b"%PDF-1.4 mock tender document", "application/pdf")
            return
        if path in ("/tenders", "/"):
            html = mock_data.LISTING_V1 if STATE["version"] == 1 else mock_data.LISTING_V2
            self._send(html)
            return
        self._send("<p>Not found</p>", code=404)

    def log_message(self, *args):
        pass


def main():
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print("Mock tender portal running at http://127.0.0.1:%d/tenders" % PORT)
        print("Toggle data with http://127.0.0.1:%d/switch  (Ctrl+C to stop)" % PORT)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
