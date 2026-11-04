from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs


OUTPUT = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1
    else Path(__file__).resolve().parents[1] / "dados" / "ato_capturado.txt"
)
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8765


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        page = """<!doctype html><meta charset='utf-8'><title>Captura local</title>
        <form id='capture' method='post'><textarea id='text' name='text' autofocus></textarea>
        <button type='submit'>Salvar</button></form>
        <script>document.querySelector('#text').addEventListener('input', () =>
          setTimeout(() => document.querySelector('#capture').requestSubmit(), 100));</script>"""
        data = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(size).decode("utf-8"))
        text = form.get("text", [""])[0]
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(text, encoding="utf-8")
        data = f"Salvo: {len(text)} caracteres".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
