/**
 * notify.js — Pushover notifications + analytics for Homegrown 2026
 * Lightweight client-side event tracking via Pushover API.
 * No database, no server — just push notifications with JSON payloads.
 */

const PUSHOVER_USER = "uvtbp26pbssv6wj8a3qzaaj2vb4rd5";
const PUSHOVER_APP = "ahzkevqijnvm4b7r9ydd3jqitaed1n";
const NOTIFY_VERSION = "1.0.0";
const NOTIFY_COOLDOWN = 60000; // 1 min between same-type notifications (anti-spam)
const _notifyTimestamps = {};

// ---- Geo lookup (free, no API key) ----
let _geoCache = null;
async function getGeo() {
  if (_geoCache) return _geoCache;
  try {
    const r = await fetch("https://ipapi.co/json/", { signal: AbortSignal.timeout(3000) });
    const d = await r.json();
    _geoCache = {
      ip: d.ip || "unknown",
      city: d.city || "unknown",
      region: d.region || "",
      country: d.country_name || "",
      lat: d.latitude,
      lon: d.longitude,
      org: d.org || ""
    };
  } catch {
    _geoCache = { ip: "unknown", city: "unknown", region: "", country: "" };
  }
  return _geoCache;
}

// ---- Device info ----
function getDevice() {
  const ua = navigator.userAgent;
  const w = window.innerWidth, h = window.innerHeight;
  const mobile = w <= 768;
  let platform = "Desktop";
  if (/iPhone/.test(ua)) platform = "iPhone";
  else if (/iPad/.test(ua)) platform = "iPad";
  else if (/Android/.test(ua)) platform = "Android";
  return { platform, viewport: `${w}x${h}`, mobile, dpr: window.devicePixelRatio || 1 };
}

// ---- Send to Pushover ----
async function pushNotify(title, message, priority = -1, extras = {}) {
  // Rate limit by title
  const now = Date.now();
  if (_notifyTimestamps[title] && now - _notifyTimestamps[title] < NOTIFY_COOLDOWN) return;
  _notifyTimestamps[title] = now;

  // Build JSON payload for analysis
  const geo = await getGeo();
  const device = getDevice();
  const payload = {
    event: title,
    timestamp: new Date().toISOString(),
    version: NOTIFY_VERSION,
    geo,
    device,
    ...extras
  };

  const body = new FormData();
  body.append("token", PUSHOVER_APP);
  body.append("user", PUSHOVER_USER);
  body.append("title", `🎸 ${title}`);
  body.append("message", message + "\n\n📊 " + JSON.stringify(payload));
  body.append("priority", priority); // -1 = silent, 0 = normal
  body.append("sound", priority >= 0 ? "pushover" : "none");
  body.append("html", "1");

  try {
    await fetch("https://api.pushover.net/1/messages.json", {
      method: "POST",
      body
    });
  } catch { /* fail silently */ }
}

// ---- Event: Site visit ----
async function notifyVisit() {
  const geo = await getGeo();
  const device = getDevice();
  const time = new Date().toLocaleString("en-US", { timeZone: "America/Chicago" });
  const referer = document.referrer || "direct";
  pushNotify(
    "Site Visit",
    `📍 ${geo.city}, ${geo.region} ${geo.country}\n🕐 ${time}\n🌐 ${geo.ip}\n📱 ${device.platform} ${device.viewport}\n🔗 ${referer}`,
    -1, // silent
    { referer }
  );
}

// ---- Event: Set list favorite ----
function notifyFavorite(actName, venue, date, action = "added") {
  const time = new Date().toLocaleString("en-US", { timeZone: "America/Chicago" });
  const emoji = action === "added" ? "⭐" : "❌";
  pushNotify(
    `Set List ${action === "added" ? "Add" : "Remove"}`,
    `${emoji} ${actName}\n📍 ${venue}\n📅 ${date}\n🕐 ${time}`,
    -1,
    { act: actName, venue, date, action }
  );
}

// ---- Event: Set list share ----
function notifyShare(platform, setListItems) {
  const time = new Date().toLocaleString("en-US", { timeZone: "America/Chicago" });
  const acts = setListItems.map(s => s.act).join(", ");
  const count = setListItems.length;
  pushNotify(
    "Set List Shared",
    `📤 ${platform}\n🎵 ${count} acts: ${acts.slice(0, 200)}\n🕐 ${time}`,
    0, // normal priority — shares are interesting
    { platform, actCount: count, acts: setListItems.map(s => ({ act: s.act, venue: s.venue, date: s.date })) }
  );
}

// ---- Event: ICS download ----
function notifyICSDownload(setListItems) {
  const time = new Date().toLocaleString("en-US", { timeZone: "America/Chicago" });
  const count = setListItems.length;
  pushNotify(
    "Calendar Export",
    `📅 ${count} acts exported to .ics\n🕐 ${time}`,
    -1,
    { actCount: count, acts: setListItems.map(s => s.act) }
  );
}

// ---- Event: Issue report ----
function notifyIssue(description) {
  const time = new Date().toLocaleString("en-US", { timeZone: "America/Chicago" });
  const url = window.location.href;
  pushNotify(
    "⚠️ Issue Report",
    `🐛 ${description}\n🔗 ${url}\n🕐 ${time}`,
    0, // normal priority
    { description, url, userAgent: navigator.userAgent }
  );
}

// ---- Event: Video play ----
function notifyVideoPlay(actName, source) {
  pushNotify(
    "Video Play",
    `▶️ ${actName} (${source})`,
    -1,
    { act: actName, source }
  );
}
