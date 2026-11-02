"""Lancer avec python agent.py sur le PC Windows à consulter."""
import logging
import queue
import secrets
import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk

from werkzeug.serving import make_server
from server import create_app
from mailer import RECIPIENT, save_settings, load_settings, delete_settings, send_pin


class Agent:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PCDistant Wi-Fi — partage local")
        self.root.geometry("720x640")
        self.server = None
        self.worker = None
        self.events = queue.Queue()
        self.generation = 0
        self.email_status = tk.StringVar(value="E-mail : configurez Gmail pour activer l’envoi automatique")
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
        self.addresses = text or "Adresse à vérifier avec ipconfig"
        ttk.Label(frame, text=text or "Adresse introuvable : utilisez ipconfig pour trouver l'IPv4 Wi-Fi.").pack(anchor="w")
        ttk.Label(frame, text="Code d'accès à recopier sur votre téléphone :").pack(anchor="w", pady=(16, 4))
        ttk.Entry(frame, textvariable=self.code, state="readonly", width=52).pack(anchor="w")
        ttk.Label(frame, text="Réseau privé uniquement : HTTP non chiffré.\nLes captures et titres des fenêtres peuvent révéler des données privées.", wraplength=620).pack(anchor="w", pady=14)
        self.button = ttk.Button(frame, text="Activer le partage", command=self.toggle)
        self.button.pack(anchor="w")
        ttk.Label(frame, textvariable=self.state).pack(anchor="w", pady=10)
        ttk.Label(frame, textvariable=self.activity).pack(anchor="w")
        ttk.Label(frame, text="Vous pouvez réduire cette fenêtre. Fermer arrête le partage.").pack(anchor="w", pady=14)
        ttk.Label(frame, text=f"Code envoyé à : {RECIPIENT}").pack(anchor="w")
        mail_buttons = ttk.Frame(frame)
        mail_buttons.pack(anchor="w", pady=8)
        ttk.Button(mail_buttons, text="Configurer Gmail", command=self.configure_mail).pack(side="left")
        ttk.Button(mail_buttons, text="Désactiver l'envoi", command=self.disable_mail).pack(side="left", padx=8)
        ttk.Label(frame, textvariable=self.email_status, wraplength=660).pack(anchor="w")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(200, self.drain_events)

    def drain_events(self):
        try:
            while True:
                message = self.events.get_nowait()
                if isinstance(message, tuple):
                    generation, status = message
                    if generation == self.generation:
                        self.email_status.set(status)
                else:
                    self.activity.set(f"{datetime.now():%H:%M:%S} — {message}")
        except queue.Empty:
            pass
        self.root.after(200, self.drain_events)

    def configure_mail(self):
        sender = simpledialog.askstring("Gmail", "Adresse Gmail expéditrice :", initialvalue=RECIPIENT, parent=self.root)
        if not sender:
            return
        password = simpledialog.askstring(
            "Mot de passe d'application Google",
            "Activez la validation en deux étapes sur Google, puis créez un mot de passe d'application.\n"
            "Saisissez ses 16 caractères ici uniquement (pas votre mot de passe habituel) :",
            show="*", parent=self.root)
        if not password:
            return
        try:
            save_settings(sender, password)
        except ValueError as error:
            messagebox.showerror("Gmail", str(error), parent=self.root)
            return
        except Exception:
            messagebox.showerror("Gmail", "Enregistrement impossible dans le gestionnaire d'identifiants Windows.", parent=self.root)
            return
        self.email_status.set("Gmail configuré. Envoi automatique à la prochaine activation du partage.")

    def disable_mail(self):
        try:
            delete_settings()
        except Exception:
            messagebox.showerror("Gmail", "Impossible de supprimer les identifiants du coffre Windows.", parent=self.root)
            return
        self.email_status.set("Envoi automatique désactivé. Un message déjà en cours d'envoi ne peut pas être rappelé.")

    def email_pin(self, token, generation):
        try:
            settings = load_settings()
            if settings is None:
                status = "E-mail non configuré. Le code reste disponible à l'écran."
            elif generation != self.generation:
                return
            else:
                send_pin(settings, token, self.addresses)
                status = "Code transmis à Gmail pour " + RECIPIENT + ". Vérifiez aussi les spams."
        except Exception:
            # Ne jamais afficher une exception SMTP : elle peut contenir des données privées.
            status = "Échec de l'envoi : vérifiez Internet et le mot de passe d'application Gmail. Le partage Wi-Fi reste actif."
        self.events.put((generation, status))

    def toggle(self):
        if self.server:
            self.stop()
            return
        token = f"{secrets.randbelow(10000):04d}"
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
        self.generation += 1
        self.email_status.set("Vérification de Gmail et envoi du code…")
        threading.Thread(target=self.email_pin, args=(token, self.generation), daemon=True).start()

    def stop(self):
        self.generation += 1
        self.email_status.set("Partage arrêté. Les codes des anciens messages ne sont plus valables pour cette session.")
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
