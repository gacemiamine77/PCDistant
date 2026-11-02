"""Envoi Gmail TLS ; secrets stockés exclusivement dans le coffre Windows."""
import json
import re
import smtplib
import socket
import ssl
from datetime import datetime
from email.message import EmailMessage

RECIPIENT = "gacemiamine@gmail.com"
SERVICE = "PCDistant-WiFi-Gmail"
ACCOUNT = "smtp-config"


def _vault():
    # Pas de backend texte ni de repli vers un fichier local.
    from keyring.backends.Windows import WinVaultKeyring
    return WinVaultKeyring()


def save_settings(sender, password):
    sender = sender.strip()
    password = password.replace(" ", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:gmail\.com|googlemail\.com)", sender, re.IGNORECASE):
        raise ValueError("Indiquez l'adresse Gmail du compte expéditeur.")
    if not re.fullmatch(r"[A-Za-z0-9]{16}", password):
        raise ValueError("Utilisez un mot de passe d'application Google de 16 caractères, pas votre mot de passe habituel.")
    _vault().set_password(SERVICE, ACCOUNT, json.dumps({"sender": sender, "password": password}))


def load_settings():
    data = _vault().get_password(SERVICE, ACCOUNT)
    return json.loads(data) if data else None


def delete_settings():
    vault = _vault()
    if vault.get_password(SERVICE, ACCOUNT) is not None:
        vault.delete_password(SERVICE, ACCOUNT)


def send_pin(settings, pin, addresses):
    message = EmailMessage()
    message["From"] = settings["sender"]
    message["To"] = RECIPIENT
    message["Subject"] = "PCDistant — code de partage Wi-Fi"
    message.set_content(
        f"Partage activé sur {socket.gethostname()} à {datetime.now():%Y-%m-%d %H:%M:%S}.\n\n"
        f"Code d'accès : {pin}\n\n"
        f"Adresses locales (même réseau Wi-Fi uniquement) :\n{addresses}\n\n"
        "Le code est valable pendant cette activation du partage. "
        "Un ancien message peut contenir un code expiré.\n"
        "Aucune capture ni liste d'applications n'est jointe.\n"
    )
    # Certificat et nom d'hôte vérifiés ; aucune connexion SMTP en clair.
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15, context=ssl.create_default_context()) as smtp:
        smtp.login(settings["sender"], settings["password"])
        smtp.send_message(message)
