"""Un vrai petit serveur IMAP (socket + protocole réel), pour tester notre
ClientImap sans dépendre d'un compte Gmail réel. Ne couvre que les commandes
que notre client utilise : LOGIN, SELECT, UID SEARCH ALL, UID FETCH, LOGOUT."""

import socket
import threading


class FauxServeurImap:
    def __init__(self, messages: dict[str, bytes], utilisateur: str, mot_de_passe: str):
        self.messages = messages
        self.utilisateur = utilisateur
        self.mot_de_passe = mot_de_passe

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind(("127.0.0.1", 0))
        self._socket.listen(1)
        self.port = self._socket.getsockname()[1]

        self._arret = threading.Event()
        self._thread = threading.Thread(target=self._boucle, daemon=True)

    def __enter__(self) -> "FauxServeurImap":
        self._thread.start()
        return self

    def __exit__(self, *_exc) -> None:
        self._arret.set()
        try:
            self._socket.close()
        except OSError:
            pass

    def _boucle(self) -> None:
        self._socket.settimeout(0.5)
        while not self._arret.is_set():
            try:
                conn, _ = self._socket.accept()
            except (TimeoutError, OSError):
                continue
            try:
                self._gerer_connexion(conn)
            except Exception:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def _gerer_connexion(self, conn: socket.socket) -> None:
        flux = conn.makefile("rwb")
        flux.write(b"* OK IMAP4rev1 Service Ready\r\n")
        flux.flush()

        while True:
            ligne = flux.readline()
            if not ligne:
                break
            texte = ligne.decode(errors="replace").strip()
            if not texte:
                continue

            parties = texte.split(" ", 2)
            tag = parties[0]
            commande = parties[1].upper() if len(parties) > 1 else ""
            reste = parties[2] if len(parties) > 2 else ""

            if commande == "CAPABILITY":
                flux.write(b"* CAPABILITY IMAP4rev1\r\n")
                flux.write(f"{tag} OK CAPABILITY completed\r\n".encode())

            elif commande == "LOGIN":
                identifiants = [p.strip('"') for p in reste.split(" ", 1)]
                if len(identifiants) == 2 and identifiants == [self.utilisateur, self.mot_de_passe]:
                    flux.write(f"{tag} OK LOGIN completed\r\n".encode())
                else:
                    flux.write(f"{tag} NO LOGIN failed\r\n".encode())

            elif commande == "SELECT":
                flux.write(f"* {len(self.messages)} EXISTS\r\n".encode())
                flux.write(b"* 0 RECENT\r\n")
                flux.write(f"{tag} OK [READ-WRITE] SELECT completed\r\n".encode())

            elif commande == "UID":
                sous_commande, _, sous_reste = reste.partition(" ")
                sous_commande = sous_commande.upper()
                if sous_commande == "SEARCH":
                    uids = " ".join(self.messages.keys())
                    flux.write(f"* SEARCH {uids}\r\n".encode())
                    flux.write(f"{tag} OK SEARCH completed\r\n".encode())
                elif sous_commande == "FETCH":
                    uid = sous_reste.split(" ", 1)[0]
                    donnees = self.messages.get(uid, b"")
                    flux.write(f"* 1 FETCH (UID {uid} RFC822 {{{len(donnees)}}}\r\n".encode())
                    flux.write(donnees)
                    flux.write(b")\r\n")
                    flux.write(f"{tag} OK FETCH completed\r\n".encode())
                else:
                    flux.write(f"{tag} BAD unknown UID subcommand\r\n".encode())

            elif commande == "LOGOUT":
                flux.write(b"* BYE logging out\r\n")
                flux.write(f"{tag} OK LOGOUT completed\r\n".encode())
                flux.flush()
                break

            else:
                flux.write(f"{tag} BAD unknown command\r\n".encode())

            flux.flush()

        try:
            flux.close()
        except OSError:
            pass
