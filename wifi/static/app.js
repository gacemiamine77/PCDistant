"use strict";
const el = id => document.getElementById(id);
let imageUrl = null;
let busy = false;
let generation = 0;
async function requestData(capture) {
  if (busy) return;
  const token = el("code").value.trim();
  if (!/^[a-fA-F0-9]{32}$/.test(token)) {
    el("status").textContent = "Recopiez les 32 caractères du code affiché sur le PC.";
    return;
  }
  const current = generation;
  busy = true;
  el("capture").disabled = el("apps").disabled = true;
  el("status").textContent = "Demande en cours…";
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 20000);
  try {
    const response = await fetch(capture ? "/api/screenshot" : "/api/apps", {
      headers: {Authorization: "Bearer " + token}, cache: "no-store", signal: controller.signal,
      credentials: "omit", redirect: "error"
    });
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.error || "Le PC n'a pas pu répondre.");
    }
    if (capture) {
      const blob = await response.blob();
      if (current !== generation) return;
      if (imageUrl) URL.revokeObjectURL(imageUrl);
      imageUrl = URL.createObjectURL(blob);
      el("screen").src = imageUrl;
      el("image-link").href = imageUrl;
      el("image-link").hidden = false;
      el("empty").hidden = true;
    } else {
      const apps = await response.json();
      if (current !== generation) return;
      el("list").replaceChildren();
      for (const app of apps) {
        const row = document.createElement("li");
        const title = document.createElement("strong");
        const detail = document.createElement("span");
        title.textContent = `${app.name} · PID ${app.id}`;
        detail.textContent = app.title;
        row.append(title, detail);
        el("list").append(row);
      }
      if (!apps.length) el("list").textContent = "Aucune fenêtre visible.";
    }
    el("status").textContent = "Reçu à " + new Date().toLocaleTimeString("fr-FR");
  } catch (error) {
    if (current === generation) el("status").textContent = error.name === "AbortError"
      ? "Délai dépassé. Vérifiez le Wi-Fi et le partage sur le PC."
      : (error instanceof TypeError ? "Connexion perdue. Vérifiez le partage et le Wi-Fi." : error.message);
  } finally {
    clearTimeout(timeout);
    busy = false;
    el("capture").disabled = el("apps").disabled = false;
  }
}
el("capture").addEventListener("click", () => requestData(true));
el("apps").addEventListener("click", () => requestData(false));
el("clear").addEventListener("click", () => {
  generation++;
  el("code").value = "";
  el("screen").removeAttribute("src");
  el("image-link").removeAttribute("href");
  el("image-link").hidden = true;
  el("empty").hidden = false;
  el("list").textContent = "Aucune liste demandée.";
  if (imageUrl) URL.revokeObjectURL(imageUrl);
  imageUrl = null;
  el("status").textContent = "Code et données effacés.";
});
