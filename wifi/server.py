"""Agent local : aucune capture automatique, aucune sauvegarde sur disque."""
import hmac
import io
import sys
import threading
import time
from functools import wraps

from flask import Flask, Response, jsonify, render_template, request


def capture_screen():
    import mss
    from PIL import Image

    with mss.mss() as display:
        shot = display.grab(display.monitors[1])
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()


def list_apps():
    """Fenêtres visibles uniquement, pas les processus d'arrière-plan."""
    if sys.platform != "win32":
        raise RuntimeError("Cette version de l'agent nécessite Windows.")
    import ctypes
    from ctypes import wintypes
    import psutil

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    result = []

    @callback_type
    def visit(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not length:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        try:
            name = psutil.Process(pid.value).name()
        except (psutil.Error, OSError):
            return True
        result.append({"id": pid.value, "name": name, "title": title.value})
        return True

    user32.EnumWindows(visit, 0)
    return sorted(result, key=lambda app: (app["name"].lower(), app["title"]))


def create_app(token, notify=lambda message: None, capture=capture_screen, applications=list_apps):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024
    # Limite globale (pas uniquement par IP) pour protéger le petit espace des PIN.
    auth_lock = threading.Lock()
    failed_attempts = 0
    blocked_until = 0.0
    capture_lock = threading.Lock()
    last_capture = [float("-inf")]

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'"
        )
        return response

    def authenticated(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            nonlocal failed_attempts, blocked_until
            supplied = request.headers.get("Authorization", "").encode("utf-8")
            with auth_lock:
                now = time.monotonic()
                if now < blocked_until:
                    response = jsonify(error="Trop de tentatives. Réessayez dans 60 secondes.")
                    response.status_code = 429
                    response.headers["Retry-After"] = str(max(1, int(blocked_until - now + 0.999)))
                    return response
                if not hmac.compare_digest(supplied, ("Bearer " + token).encode("utf-8")):
                    failed_attempts += 1
                    if failed_attempts >= 5:
                        failed_attempts = 0
                        blocked_until = now + 60
                        response = jsonify(error="5 codes incorrects : accès bloqué pendant 60 secondes.")
                        response.status_code = 429
                        response.headers["Retry-After"] = "60"
                        return response
                    return jsonify(error="Code d'accès incorrect."), 401
                failed_attempts = 0
            return function(*args, **kwargs)
        return wrapped

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/apps")
    @authenticated
    def apps():
        try:
            data = applications()
            notify("Liste des applications demandée")
            return jsonify(data)
        except Exception:
            return jsonify(error="Liste indisponible. L'agent doit être exécuté sous Windows."), 503

    @app.get("/api/screenshot")
    @authenticated
    def screenshot():
        if not capture_lock.acquire(blocking=False):
            return jsonify(error="Une capture est déjà en cours."), 429
        try:
            if time.monotonic() - last_capture[0] < 1:
                return jsonify(error="Attendez une seconde entre deux captures."), 429
            last_capture[0] = time.monotonic()
            data = capture()
            notify("Capture d'écran demandée")
            return Response(data, mimetype="image/png")
        except Exception:
            return jsonify(error="Capture impossible. Vérifiez que la session est ouverte et déverrouillée."), 503
        finally:
            capture_lock.release()

    return app
