"""Lancer avec python agent.py sur le PC Windows à consulter."""
import logging
import queue
import secrets
import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from werkzeug.serving import make_server
from server import create_app


class Agent:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PCDistant Wi-Fi — partage local")
        self.root.geometry("690x490")
        self.server = None
        self.worker = None
        self.events = queue.Queue()
        self.code = tk.StringVar(value="Activez le partage pour obtenir un code")
        self.state = tk.StringVar(value="Partage arrêté")
        self.activity = tk.StringVar(value="Aucune demande reçue")
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="PCDistant · Wi-Fi", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Sur Android : ouvrez l'adresse du PC dans Chrome.").pack(anchor="w", pady=12)
        addresses = set()
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(socket.gethostname(), 5080, socket.AF_INET)}
        except OSError:
            pass
        addresses.discard("127.0.0.1")
        text = "\n".join(f"http://{ip}:5080" for ip in sorted(addresses))
        ttk.Label(frame, text=text or "Adresse introuvable : utilisez ipconfig pour trouver l'IPv4 Wi-Fi.").pack(anchor="w")
        ttk.Label(frame, text="Code d'accès à recopier sur votre téléphone :").pack(anchor="w", pady=(16, 4))
        ttk.Entry(frame, textvariable=self.code, state="readonly", width=52).pack(anchor="w")
        ttk.Label(frame, text="Réseau privé uniquement : HTTP non chiffré.\nLes captures et titres des fenêtres peuvent révéler des données privées.", wraplength=620).pack(anchor="w", pady=14)
        self.button = ttk.Button(frame, text="Activer le partage", command=self.toggle)
        self.button.pack(anchor="w")
        ttk.Label(frame, textvariable=self.state).pack(anchor="w", pady=10)
        ttk.Label(frame, textvariable=self.activity).pack(anchor="w")
        ttk.Label(frame, text="Vous pouvez réduire cette fenêtre. Fermer arrête le partage.").pack(anchor="w", pady=14)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(200, self.drain_events)

    def drain_events(self):
        try:
            while True:
                message = self.events.get_nowait()
                self.activity.set(f"{datetime.now():%H:%M:%S} — {message}")
        except queue.Empty:
            pass
        self.root.after(200, self.drain_events)

    def toggle(self):
        if self.server:
            self.stop()
            return
        token = secrets.token_hex(16)
        try:
            app = create_app(token, notify=self.events.put)
            # Pas de journaux de requêtes ni de mode debug exposé sur le réseau.
            logging.getLogger("werkzeug").setLevel(logging.ERROR)
            self.server = make_server("0.0.0.0", 5080, app, threaded=True)
            self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.worker.start()
        except (Exception, SystemExit):
            self.server = None
            messagebox.showerror("PCDistant", "Impossible d'ouvrir le port 5080. Arrêtez l'autre hôte PCDistant ou l'application qui utilise ce port.")
            return
        self.code.set(token)
        self.state.set("● Partage actif sur le réseau local")
        self.button.config(text="Arrêter le partage")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        self.code.set("Partage arrêté — ancien code révoqué")
        self.state.set("Partage arrêté")
        self.button.config(text="Activer le partage")

    def close(self):
        self.stop()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Agent().run()
