/*
 * This worker only sends anonymous event IDs to the loopback FUSAA API.
 * It never receives a WhatsApp message body, chat name, phone number, or file.
 */
// FUSAA server on the local network. Change this value if the server IP changes.
const API_ROOT = "http://192.168.1.68:8000/api/v1/browser-link";
const STATE_KEY = "fusaaWhatsAppLocalLink";
const HEARTBEAT_ALARM = "fusaa-whatsapp-heartbeat";
const PAGE_SIGNAL_MAX_AGE_MS = 70_000;
const MAX_PENDING_EVENTS = 100;

const EMPTY_STATE = Object.freeze({
  credential: "",
  pairedAt: null,
  pageReady: false,
  pageSignalAt: null,
  lastHeartbeatAt: null,
  lastError: "",
  eventQueue: []
});

let stateWrites = Promise.resolve();
let flushing = false;

function cleanState(value) {
  const source = value && typeof value === "object" ? value : {};
  return {
    ...EMPTY_STATE,
    ...source,
    credential: typeof source.credential === "string" ? source.credential : "",
    eventQueue: Array.isArray(source.eventQueue) ? source.eventQueue.slice(-MAX_PENDING_EVENTS) : []
  };
}

async function readState() {
  await stateWrites;
  const stored = await chrome.storage.local.get({ [STATE_KEY]: EMPTY_STATE });
  return cleanState(stored[STATE_KEY]);
}

function mutateState(mutator) {
  const operation = stateWrites.then(async () => {
    const stored = await chrome.storage.local.get({ [STATE_KEY]: EMPTY_STATE });
    const next = cleanState(mutator(cleanState(stored[STATE_KEY])));
    await chrome.storage.local.set({ [STATE_KEY]: next });
    return next;
  });
  stateWrites = operation.catch(() => undefined);
  return operation;
}

function publicStatus(state) {
  const lastSignalAge = state.pageSignalAt ? Date.now() - Date.parse(state.pageSignalAt) : Infinity;
  return {
    paired: Boolean(state.credential),
    pageReady: Boolean(state.pageReady && lastSignalAge < PAGE_SIGNAL_MAX_AGE_MS),
    lastHeartbeatAt: state.lastHeartbeatAt,
    lastError: state.lastError,
    queuedEvents: state.eventQueue.length
  };
}

function errorWithStatus(message, status) {
  const error = new Error(message);
  error.status = status;
  return error;
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      method: "POST",
      cache: "no-store",
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      }
    });
  } catch {
    throw errorWithStatus("FUSAA est inaccessible sur 192.168.1.68:8000.", 0);
  }

  let payload = {};
  try {
    payload = await response.json();
  } catch {
    // The status is sufficient for the extension; no response text is retained.
  }
  if (!response.ok) {
    throw errorWithStatus(payload.detail || "La liaison FUSAA a refusé la demande.", response.status);
  }
  return payload;
}

async function authenticatedRequest(path, body, credential) {
  return request(path, {
    headers: { "X-Fusaa-Link": credential },
    body: JSON.stringify(body)
  });
}

function activePageReady(state) {
  if (!state.pageReady || !state.pageSignalAt) return false;
  return Date.now() - Date.parse(state.pageSignalAt) < PAGE_SIGNAL_MAX_AGE_MS;
}

async function sendHeartbeat() {
  const state = await readState();
  if (!state.credential) return publicStatus(state);

  try {
    await authenticatedRequest("/heartbeat", { page_ready: activePageReady(state) }, state.credential);
    const next = await mutateState(current => ({
      ...current,
      lastHeartbeatAt: new Date().toISOString(),
      lastError: ""
    }));
    return publicStatus(next);
  } catch (error) {
    const message = error.message || "Échec du signal FUSAA.";
    const next = await mutateState(current => ({
      ...current,
      credential: error.status === 401 || error.status === 403 ? "" : current.credential,
      pairedAt: error.status === 401 || error.status === 403 ? null : current.pairedAt,
      eventQueue: error.status === 401 || error.status === 403 ? [] : current.eventQueue,
      lastError: error.status === 401 || error.status === 403
        ? "La liaison a expiré. Créez un nouveau code dans FUSAA."
        : message
    }));
    return publicStatus(next);
  }
}

function sanitizeEvent(message) {
  const kind = message?.kind === "UNREAD" ? "UNREAD" : message?.kind === "MESSAGE" ? "MESSAGE" : null;
  const eventId = typeof message?.eventId === "string" ? message.eventId.trim() : "";
  const count = Number(message?.count);
  if (!kind || !/^[a-zA-Z0-9_-]{10,128}$/.test(eventId) || !Number.isInteger(count) || count < 1 || count > 999) {
    return null;
  }
  return { eventId, kind, count };
}

async function enqueueEvent(message) {
  const event = sanitizeEvent(message);
  if (!event) throw new Error("Événement WhatsApp non valide.");

  const prior = await readState();
  if (!prior.credential) return { ignored: "not_paired" };

  await mutateState(current => {
    if (current.eventQueue.some(item => item.eventId === event.eventId)) return current;
    return {
      ...current,
      eventQueue: [...current.eventQueue, { ...event, detectedAt: new Date().toISOString() }].slice(-MAX_PENDING_EVENTS)
    };
  });
  await flushEvents();
  return { queued: true };
}

async function flushEvents() {
  if (flushing) return;
  flushing = true;
  try {
    while (true) {
      const state = await readState();
      const event = state.eventQueue[0];
      if (!state.credential || !event) return;

      try {
        await authenticatedRequest("/events", {
          event_id: event.eventId,
          kind: event.kind,
          count: event.count
        }, state.credential);
      } catch (error) {
        const message = error.status === 401 || error.status === 403
          ? "La liaison a expiré. Créez un nouveau code dans FUSAA."
          : (error.message || "Événement en attente de FUSAA.");
        await mutateState(current => ({
          ...current,
          credential: error.status === 401 || error.status === 403 ? "" : current.credential,
          pairedAt: error.status === 401 || error.status === 403 ? null : current.pairedAt,
          eventQueue: error.status === 401 || error.status === 403 ? [] : current.eventQueue,
          lastError: message
        }));
        return;
      }

      await mutateState(current => ({
        ...current,
        eventQueue: current.eventQueue.filter(item => item.eventId !== event.eventId),
        lastError: ""
      }));
    }
  } finally {
    flushing = false;
  }
}

async function pair(code) {
  const normalizedCode = typeof code === "string" ? code.trim() : "";
  if (normalizedCode.length < 20 || normalizedCode.length > 100) {
    throw new Error("Le code de liaison FUSAA est incomplet.");
  }
  const response = await request("/pair", { body: JSON.stringify({ code: normalizedCode }) });
  if (typeof response.credential !== "string" || response.credential.length < 20) {
    throw new Error("FUSAA n’a pas retourné de liaison valide.");
  }
  await mutateState(current => ({
    ...current,
    credential: response.credential,
    pairedAt: new Date().toISOString(),
    lastError: ""
  }));
  await sendHeartbeat();
  await flushEvents();
  return publicStatus(await readState());
}

async function unpair() {
  const current = await readState();
  if (current.credential) {
    try {
      await authenticatedRequest("/unpair", {}, current.credential);
    } catch (error) {
      // A rejected token is already unusable.  A network failure is kept so
      // the user can retry rather than being told the server was revoked.
      if (error.status !== 401 && error.status !== 403) throw error;
    }
  }
  await mutateState(existing => ({ ...EMPTY_STATE, pageReady: existing.pageReady, pageSignalAt: existing.pageSignalAt }));
  return publicStatus(await readState());
}

async function setPageStatus(message, sender) {
  if (!sender.url || !sender.url.startsWith("https://web.whatsapp.com/")) {
    throw new Error("Source WhatsApp Web requise.");
  }
  const pageReady = Boolean(message?.pageReady);
  await mutateState(current => ({
    ...current,
    pageReady,
    pageSignalAt: new Date().toISOString()
  }));
  return sendHeartbeat();
}

function isWhatsAppSender(sender) {
  return Boolean(sender.url && sender.url.startsWith("https://web.whatsapp.com/"));
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    switch (message?.type) {
      case "FUSAA_GET_STATUS":
        return publicStatus(await readState());
      case "FUSAA_PAIR":
        return await pair(message.code);
      case "FUSAA_UNPAIR":
        return await unpair();
      case "FUSAA_PAGE_STATUS":
        return await setPageStatus(message, sender);
      case "FUSAA_WHATSAPP_EVENT":
        if (!isWhatsAppSender(sender)) throw new Error("Source WhatsApp Web requise.");
        return await enqueueEvent(message);
      default:
        throw new Error("Commande d’extension inconnue.");
    }
  })().then(
    result => sendResponse({ ok: true, result }),
    error => sendResponse({ ok: false, error: error.message || "Erreur de l’extension." })
  );
  return true;
});

function ensureHeartbeatAlarm() {
  chrome.alarms.create(HEARTBEAT_ALARM, { periodInMinutes: 1 });
}

chrome.runtime.onInstalled.addListener(() => {
  ensureHeartbeatAlarm();
  void flushEvents();
});
chrome.runtime.onStartup.addListener(() => {
  ensureHeartbeatAlarm();
  void flushEvents();
});
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name !== HEARTBEAT_ALARM) return;
  void sendHeartbeat();
  void flushEvents();
});

ensureHeartbeatAlarm();
