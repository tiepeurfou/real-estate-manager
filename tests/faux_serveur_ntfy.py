"""Un vrai petit serveur HTTP (socket réel), pour tester notre client ntfy
sans dépendre du vrai ntfy.sh. Capture les requêtes reçues pour inspection."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class FauxServeurNtfy:
    def __init__(self, code_reponse: int = 200):
        self.requetes: list[dict] = []
        self._code_reponse = code_reponse

        requetes = self.requetes
        code_reponse = self._code_reponse

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                longueur = int(self.headers.get("Content-Length", 0))
                corps = self.rfile.read(longueur)
                requetes.append(
                    {
                        "content_type": self.headers.get("Content-Type"),
                        "json": json.loads(corps.decode("utf-8")) if corps else None,
                    }
                )
                self.send_response(code_reponse)
                self.end_headers()

            def log_message(self, *_args):
                pass

        self._serveur = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._serveur.server_port
        self._thread = threading.Thread(target=self._serveur.serve_forever, daemon=True)

    def __enter__(self) -> "FauxServeurNtfy":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._serveur.shutdown()
        self._serveur.server_close()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"
