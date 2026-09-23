// Zugriffsschutz für die Doku-Seite auf Cloudflare Pages.
//
// Jede Anfrage läuft zuerst hier durch, auch die für statische Dateien.
// Durch darf nur, wer sich über Forgejo anmeldet UND das Repo lesen darf.
// Geprüft wird das mit dem Token des Besuchers gegen
// GET /api/v1/repos/<FORGEJO_REPO>; der Token wird danach verworfen.
//
// Grundsatz: im Zweifel ablehnen. Fehlende Konfiguration -> 500, ungültiges
// oder abgelaufenes Cookie -> neue Anmeldung, Fehler bei Forgejo -> 502.
// Nie wird eine Seite ohne gültige Sitzung ausgeliefert.
//
// Konfiguration (Umgebungsvariablen des Pages-Projekts, docs/HOSTING.md):
//   OAUTH_CLIENT_ID      Client-ID der OAuth2-Anwendung in Forgejo
//   OAUTH_CLIENT_SECRET  Client-Secret (als Secret hinterlegt)
//   SESSION_SECRET       mindestens 32 Zeichen, signiert die Cookies (Secret)
//   FORGEJO_URL          optional, Standard unten
//   FORGEJO_REPO         optional, Standard unten
//   OAUTH_SCOPE          optional, Standard "read:repository"

const DEFAULT_FORGEJO_URL = "https://ds1515.me-systeme.de";
const DEFAULT_FORGEJO_REPO = "l.hentschke/picam-ai";

export const SESSION_COOKIE = "__Host-docs_session";
export const LOGIN_COOKIE = "__Host-docs_login";
export const CALLBACK_PATH = "/_auth/callback";
export const LOGOUT_PATH = "/_auth/logout";
const SESSION_SECONDS = 8 * 3600; // Rechteentzug in Forgejo wirkt spätestens nach 8 h
const LOGIN_SECONDS = 600;

export async function onRequest(context) {
  const { request, env, next } = context;
  let cfg;
  try {
    cfg = await loadConfig(env);
  } catch (err) {
    return page(500, "Doku-Seite nicht konfiguriert", String(err.message || err));
  }
  const url = new URL(request.url);

  if (url.pathname === CALLBACK_PATH) return callback(request, url, cfg);
  if (url.pathname === LOGOUT_PATH) {
    return new Response(null, {
      status: 302,
      headers: [["Location", "/"], ["Set-Cookie", clearCookie(SESSION_COOKIE)], ...securityHeaders()],
    });
  }

  const session = await readSigned(getCookie(request, SESSION_COOKIE), cfg.key);
  if (session && typeof session.exp === "number" && session.exp > nowSeconds()) {
    return privatize(await next());
  }

  if (request.method !== "GET" && request.method !== "HEAD") {
    return page(401, "Anmeldung erforderlich", "Bitte die Seite neu laden und über Forgejo anmelden.");
  }
  return startLogin(url, cfg);
}

// --- Anmeldung -------------------------------------------------------------

async function startLogin(url, cfg) {
  const state = randomToken();
  const verifier = randomToken();
  const challenge = b64url(new Uint8Array(await crypto.subtle.digest("SHA-256", enc(verifier))));
  const returnTo = safeReturnPath(url.pathname + url.search);
  const login = await sign({ s: state, v: verifier, r: returnTo, exp: nowSeconds() + LOGIN_SECONDS }, cfg.key);

  const authorize = new URL("/login/oauth/authorize", cfg.forgejo);
  authorize.search = new URLSearchParams({
    client_id: cfg.clientId,
    redirect_uri: url.origin + CALLBACK_PATH,
    response_type: "code",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
    scope: cfg.scope,
  }).toString();

  return new Response(null, {
    status: 302,
    headers: [
      ["Location", authorize.toString()],
      ["Set-Cookie", cookie(LOGIN_COOKIE, login, LOGIN_SECONDS)],
      ...securityHeaders(),
    ],
  });
}

async function callback(request, url, cfg) {
  const login = await readSigned(getCookie(request, LOGIN_COOKIE), cfg.key);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");
  if (!login || !(login.exp > nowSeconds()) || !code || !state || !timingSafeEqual(state, login.s)) {
    return page(400, "Anmeldung ungültig oder abgelaufen", 'Bitte <a href="/">neu beginnen</a>.');
  }

  let token;
  try {
    const res = await fetch(new URL("/login/oauth/access_token", cfg.forgejo), {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded", Accept: "application/json" },
      body: new URLSearchParams({
        grant_type: "authorization_code",
        code,
        redirect_uri: url.origin + CALLBACK_PATH,
        client_id: cfg.clientId,
        client_secret: cfg.clientSecret,
        code_verifier: login.v,
      }),
    });
    if (!res.ok) return page(502, "Forgejo hat die Anmeldung abgelehnt", `Token-Austausch: HTTP ${res.status}`);
    token = (await res.json()).access_token;
  } catch {
    return page(502, "Forgejo nicht erreichbar", "Bitte später erneut versuchen.");
  }
  if (!token) return page(502, "Forgejo hat keinen Token geliefert", "");

  const auth = { Authorization: `Bearer ${token}`, Accept: "application/json" };
  let user;
  try {
    const repo = await fetch(new URL(`/api/v1/repos/${cfg.repo}`, cfg.forgejo), { headers: auth });
    if (repo.status === 403 || repo.status === 404) {
      return page(403, "Kein Zugriff", `Dein Forgejo-Konto darf <code>${escapeHtml(cfg.repo)}</code> nicht lesen.`);
    }
    if (!repo.ok) return page(502, "Rechteprüfung fehlgeschlagen", `Forgejo: HTTP ${repo.status}`);
    const perms = (await repo.json()).permissions || {};
    if (perms.pull !== true) {
      return page(403, "Kein Zugriff", `Dein Forgejo-Konto darf <code>${escapeHtml(cfg.repo)}</code> nicht lesen.`);
    }
    const me = await fetch(new URL("/api/v1/user", cfg.forgejo), { headers: auth });
    user = me.ok ? (await me.json()).login : undefined;
  } catch {
    return page(502, "Forgejo nicht erreichbar", "Bitte später erneut versuchen.");
  }

  const session = await sign({ u: user || "?", exp: nowSeconds() + SESSION_SECONDS }, cfg.key);
  return new Response(null, {
    status: 302,
    headers: [
      ["Location", safeReturnPath(login.r)],
      ["Set-Cookie", cookie(SESSION_COOKIE, session, SESSION_SECONDS)],
      ["Set-Cookie", clearCookie(LOGIN_COOKIE)],
      ...securityHeaders(),
    ],
  });
}

// --- Konfiguration -----------------------------------------------------------

async function loadConfig(env) {
  const need = (name) => {
    const value = env && env[name];
    if (!value) throw new Error(`${name} fehlt`);
    return String(value);
  };
  const secret = need("SESSION_SECRET");
  if (secret.length < 32) throw new Error("SESSION_SECRET ist kürzer als 32 Zeichen");
  const key = await crypto.subtle.importKey("raw", enc(secret), { name: "HMAC", hash: "SHA-256" }, false, [
    "sign",
    "verify",
  ]);
  const repo = String(env.FORGEJO_REPO || DEFAULT_FORGEJO_REPO);
  // owner/name, keiner der beiden Teile darf mit "." beginnen (kein "../x").
  if (!/^[\w-][\w.-]*\/[\w-][\w.-]*$/.test(repo)) throw new Error("FORGEJO_REPO ungültig");
  return {
    key,
    clientId: need("OAUTH_CLIENT_ID"),
    clientSecret: need("OAUTH_CLIENT_SECRET"),
    forgejo: String(env.FORGEJO_URL || DEFAULT_FORGEJO_URL),
    repo,
    scope: String(env.OAUTH_SCOPE || "read:repository"),
  };
}

// --- Signierte Cookies -------------------------------------------------------

export async function sign(payload, key) {
  const body = b64url(enc(JSON.stringify(payload)));
  const mac = new Uint8Array(await crypto.subtle.sign("HMAC", key, enc(body)));
  return `${body}.${b64url(mac)}`;
}

export async function readSigned(value, key) {
  if (!value || typeof value !== "string") return null;
  const parts = value.split(".");
  if (parts.length !== 2) return null;
  let mac;
  try {
    mac = fromB64url(parts[1]);
  } catch {
    return null;
  }
  // crypto.subtle.verify vergleicht in konstanter Zeit.
  const ok = await crypto.subtle.verify("HMAC", key, mac, enc(parts[0]));
  if (!ok) return null;
  try {
    return JSON.parse(new TextDecoder().decode(fromB64url(parts[0])));
  } catch {
    return null;
  }
}

function cookie(name, value, maxAge) {
  // __Host-: nur über HTTPS, Path=/, ohne Domain - gilt nur für genau diesen Host.
  return `${name}=${value}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${maxAge}`;
}

function clearCookie(name) {
  return `${name}=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0`;
}

export function getCookie(request, name) {
  const header = request.headers.get("Cookie") || "";
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i > 0 && part.slice(0, i).trim() === name) return part.slice(i + 1).trim();
  }
  return null;
}

// --- Hilfen ------------------------------------------------------------------

export function safeReturnPath(path) {
  // Nur Pfade dieser Seite: kein "//host", kein "\", keine absolute URL.
  if (typeof path !== "string" || !path.startsWith("/") || path.startsWith("//") || path.includes("\\")) return "/";
  if (path.startsWith(CALLBACK_PATH)) return "/";
  return path;
}

function privatize(response) {
  const res = new Response(response.body, response);
  res.headers.set("Cache-Control", "private, max-age=0, must-revalidate");
  for (const [k, v] of securityHeaders()) res.headers.set(k, v);
  return res;
}

function securityHeaders() {
  return [
    ["X-Robots-Tag", "noindex, nofollow"],
    ["Referrer-Policy", "same-origin"],
    ["X-Content-Type-Options", "nosniff"],
  ];
}

function page(status, title, html) {
  const body = `<!doctype html><html lang="de"><meta charset="utf-8"><meta name="robots" content="noindex">
<title>${escapeHtml(title)}</title><body style="font-family:system-ui;max-width:40rem;margin:4rem auto;padding:0 1rem">
<h1>${escapeHtml(title)}</h1><p>${html}</p></body></html>`;
  return new Response(body, {
    status,
    headers: [["Content-Type", "text/html; charset=utf-8"], ["Cache-Control", "no-store"], ...securityHeaders()],
  });
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

const enc = (s) => new TextEncoder().encode(s);
const nowSeconds = () => Math.floor(Date.now() / 1000);

function randomToken() {
  return b64url(crypto.getRandomValues(new Uint8Array(32)));
}

function b64url(bytes) {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromB64url(s) {
  if (!/^[A-Za-z0-9_-]*$/.test(s)) throw new Error("kein base64url");
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}
