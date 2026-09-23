// Tests für functions/_middleware.js - laufen mit `node --test cloudflare/test/middleware.test.js`
// ohne Cloudflare und ohne Netz (fetch wird ersetzt).
import { test, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import {
  onRequest,
  sign,
  SESSION_COOKIE,
  LOGIN_COOKIE,
  CALLBACK_PATH,
  LOGOUT_PATH,
  safeReturnPath,
} from "../functions/_middleware.js";

const ORIGIN = "https://picam-docs.pages.dev";
const FORGEJO = "https://forgejo.example";
const ENV = {
  OAUTH_CLIENT_ID: "client-123",
  OAUTH_CLIENT_SECRET: "geheim-456",
  SESSION_SECRET: "x".repeat(48),
  FORGEJO_URL: FORGEJO,
  FORGEJO_REPO: "l.hentschke/picam-ai",
};

let realFetch;
let fetchCalls;
beforeEach(() => {
  realFetch = globalThis.fetch;
  fetchCalls = [];
  globalThis.fetch = async () => {
    throw new Error("unerwarteter fetch");
  };
});
afterEach(() => {
  globalThis.fetch = realFetch;
});

function mockForgejo({ tokenStatus = 200, repoStatus = 200, pull = true } = {}) {
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input);
    fetchCalls.push({ url, init });
    if (url === `${FORGEJO}/login/oauth/access_token`) {
      return Response.json({ access_token: "tok-besucher" }, { status: tokenStatus });
    }
    if (url === `${FORGEJO}/api/v1/repos/l.hentschke/picam-ai`) {
      return Response.json({ permissions: { pull } }, { status: repoStatus });
    }
    if (url === `${FORGEJO}/api/v1/user`) return Response.json({ login: "l.hentschke" });
    throw new Error(`unerwarteter fetch: ${url}`);
  };
}

async function key() {
  return crypto.subtle.importKey("raw", new TextEncoder().encode(ENV.SESSION_SECRET), { name: "HMAC", hash: "SHA-256" }, false, [
    "sign",
    "verify",
  ]);
}

function run(path, { cookie, method = "GET", env = ENV } = {}) {
  const headers = cookie ? { Cookie: cookie } : {};
  let nextCalled = false;
  const context = {
    request: new Request(ORIGIN + path, { method, headers }),
    env,
    next: async () => {
      nextCalled = true;
      return new Response("GEHEIMER INHALT", { headers: { "Content-Type": "text/html" } });
    },
  };
  return onRequest(context).then((res) => ({ res, nextCalled: () => nextCalled }));
}

const setCookies = (res) => res.headers.getSetCookie();

test("ohne Sitzung: Weiterleitung zu Forgejo mit PKCE, Inhalt nie ausgeliefert", async () => {
  const { res, nextCalled } = await run("/docs/status.html?x=1");
  assert.equal(res.status, 302);
  assert.equal(nextCalled(), false);
  const loc = new URL(res.headers.get("Location"));
  assert.equal(loc.origin + loc.pathname, `${FORGEJO}/login/oauth/authorize`);
  assert.equal(loc.searchParams.get("client_id"), "client-123");
  assert.equal(loc.searchParams.get("redirect_uri"), ORIGIN + CALLBACK_PATH);
  assert.equal(loc.searchParams.get("code_challenge_method"), "S256");
  assert.ok(loc.searchParams.get("state").length >= 40);
  const [c] = setCookies(res);
  assert.match(c, new RegExp(`^${LOGIN_COOKIE}=`));
  assert.match(c, /Secure/);
  assert.match(c, /HttpOnly/);
  assert.match(c, /Path=\//);
  assert.doesNotMatch(c, /Domain=/i);
});

test("gültige Sitzung: Inhalt kommt, privat und noindex", async () => {
  const s = await sign({ u: "a", exp: Math.floor(Date.now() / 1000) + 60 }, await key());
  const { res, nextCalled } = await run("/", { cookie: `${SESSION_COOKIE}=${s}` });
  assert.equal(res.status, 200);
  assert.equal(nextCalled(), true);
  assert.equal(await res.text(), "GEHEIMER INHALT");
  assert.match(res.headers.get("Cache-Control"), /private/);
  assert.match(res.headers.get("X-Robots-Tag"), /noindex/);
});

test("abgelaufene Sitzung: neue Anmeldung", async () => {
  const s = await sign({ u: "a", exp: Math.floor(Date.now() / 1000) - 1 }, await key());
  const { res, nextCalled } = await run("/", { cookie: `${SESSION_COOKIE}=${s}` });
  assert.equal(res.status, 302);
  assert.equal(nextCalled(), false);
});

test("manipulierte oder fremd signierte Sitzung: abgelehnt", async () => {
  const s = await sign({ u: "a", exp: Math.floor(Date.now() / 1000) + 60 }, await key());
  const [body, mac] = s.split(".");
  const forged = Buffer.from(JSON.stringify({ u: "evil", exp: 9999999999 })).toString("base64url");
  const otherKey = await crypto.subtle.importKey("raw", new TextEncoder().encode("y".repeat(48)), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const foreign = await sign({ u: "a", exp: 9999999999 }, otherKey);
  for (const value of [`${forged}.${mac}`, `${body}.AAAA`, `${body}`, "", "a.b.c", foreign, "%%%.***"]) {
    const { res, nextCalled } = await run("/", { cookie: `${SESSION_COOKIE}=${value}` });
    assert.equal(res.status, 302, `Wert ${value}`);
    assert.equal(nextCalled(), false, `Wert ${value}`);
  }
});

test("fehlende oder schwache Konfiguration: 500, nie Inhalt", async () => {
  for (const env of [{}, { ...ENV, SESSION_SECRET: "kurz" }, { ...ENV, OAUTH_CLIENT_SECRET: "" }, { ...ENV, FORGEJO_REPO: "../x" }]) {
    const s = await sign({ u: "a", exp: Math.floor(Date.now() / 1000) + 60 }, await key());
    const { res, nextCalled } = await run("/", { env, cookie: `${SESSION_COOKIE}=${s}` });
    assert.equal(res.status, 500);
    assert.equal(nextCalled(), false);
  }
});

test("POST ohne Sitzung: 401 statt Weiterleitung", async () => {
  const { res, nextCalled } = await run("/", { method: "POST" });
  assert.equal(res.status, 401);
  assert.equal(nextCalled(), false);
});

async function loginCookie(overrides = {}) {
  const payload = { s: "state-abc", v: "verifier-xyz", r: "/docs/status.html", exp: Math.floor(Date.now() / 1000) + 60, ...overrides };
  return `${LOGIN_COOKIE}=${await sign(payload, await key())}`;
}

test("Rückkehr von Forgejo mit Repo-Leserecht: Sitzung und Rücksprung", async () => {
  mockForgejo();
  const { res } = await run(`${CALLBACK_PATH}?code=c1&state=state-abc`, { cookie: await loginCookie() });
  assert.equal(res.status, 302);
  assert.equal(res.headers.get("Location"), "/docs/status.html");
  const cookies = setCookies(res);
  assert.ok(cookies.some((c) => c.startsWith(`${SESSION_COOKIE}=`) && /Max-Age=28800/.test(c)));
  assert.ok(cookies.some((c) => c.startsWith(`${LOGIN_COOKIE}=;`)));
  const tokenCall = fetchCalls.find((c) => c.url.endsWith("/login/oauth/access_token"));
  const form = new URLSearchParams(tokenCall.init.body);
  assert.equal(form.get("code_verifier"), "verifier-xyz");
  assert.equal(form.get("client_secret"), "geheim-456");
  assert.equal(form.get("redirect_uri"), ORIGIN + CALLBACK_PATH);
  const repoCall = fetchCalls.find((c) => c.url.includes("/api/v1/repos/"));
  assert.equal(repoCall.init.headers.Authorization, "Bearer tok-besucher");
});

test("Rückkehr ohne Repo-Leserecht: 403, keine Sitzung", async () => {
  for (const opts of [{ repoStatus: 404 }, { repoStatus: 403 }, { pull: false }]) {
    mockForgejo(opts);
    const { res } = await run(`${CALLBACK_PATH}?code=c1&state=state-abc`, { cookie: await loginCookie() });
    assert.equal(res.status, 403, JSON.stringify(opts));
    assert.ok(!setCookies(res).some((c) => c.startsWith(`${SESSION_COOKIE}=`) && !c.includes("Max-Age=0")));
  }
});

test("Rückkehr mit falschem State, ohne oder mit abgelaufenem Login-Cookie: 400", async () => {
  mockForgejo();
  const cases = [
    { path: `${CALLBACK_PATH}?code=c1&state=anders`, cookie: await loginCookie() },
    { path: `${CALLBACK_PATH}?code=c1&state=state-abc`, cookie: undefined },
    { path: `${CALLBACK_PATH}?code=c1&state=state-abc`, cookie: await loginCookie({ exp: 1 }) },
    { path: `${CALLBACK_PATH}?state=state-abc`, cookie: await loginCookie() },
  ];
  for (const c of cases) {
    const { res } = await run(c.path, { cookie: c.cookie });
    assert.equal(res.status, 400, c.path);
  }
  assert.equal(fetchCalls.length, 0, "ohne gültigen State kein Kontakt zu Forgejo");
});

test("Forgejo lehnt Token-Austausch ab oder ist nicht erreichbar: 502", async () => {
  mockForgejo({ tokenStatus: 400 });
  let { res } = await run(`${CALLBACK_PATH}?code=c1&state=state-abc`, { cookie: await loginCookie() });
  assert.equal(res.status, 502);
  globalThis.fetch = async () => {
    throw new TypeError("network");
  };
  ({ res } = await run(`${CALLBACK_PATH}?code=c1&state=state-abc`, { cookie: await loginCookie() }));
  assert.equal(res.status, 502);
});

test("Rücksprung nur auf eigene Pfade", () => {
  for (const bad of ["//evil.example/x", "https://evil.example", "\\\\evil", "/\\evil", "evil", "", null, CALLBACK_PATH + "?x"]) {
    assert.equal(safeReturnPath(bad), "/", String(bad));
  }
  assert.equal(safeReturnPath("/docs/status.html?q=1"), "/docs/status.html?q=1");
});

test("Abmelden löscht die Sitzung", async () => {
  const { res } = await run(LOGOUT_PATH);
  assert.equal(res.status, 302);
  assert.ok(setCookies(res).some((c) => c.startsWith(`${SESSION_COOKIE}=;`) && c.includes("Max-Age=0")));
});
