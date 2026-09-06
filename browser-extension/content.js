/*
 * WhatsApp Web detector.
 * It looks only at structural DOM markers and an optional leading unread number
 * in the document title. It never reads, stores, or sends message text, names,
 * telephone numbers, message IDs, media, or file names.
 */
(() => {
  if (window.top !== window) return;

  const UNREAD_MARKERS = [
    "[data-testid='icon-unread-count']",
    "[data-testid='unread-count']",
    "[data-icon='unread-count']",
    "[data-icon='unread-filled']"
  ];
  const INCOMING_MESSAGE_MARKERS = ".message-in, [data-testid='msg-in']";
  const MAIN_INTERFACE_MARKERS = [
    "#pane-side",
    "[data-testid='chat-list']",
    "[data-testid='conversation-panel-wrapper']",
    "[data-testid='chatlist-header']"
  ];
  const STABILIZATION_DELAY_MS = 2_500;
  const CHECK_DELAY_MS = 180;
  const INCOMING_BATCH_DELAY_MS = 450;
  const EVENT_DEDUPLICATION_MS = 650;

  let pageReady = false;
  let stabilizeUntil = 0;
  let lastUnreadLevel = 0;
  let lastEventAt = 0;
  let incomingCandidates = 0;
  let checkTimer = null;
  let incomingTimer = null;

  function send(message) {
    try {
      const result = chrome.runtime.sendMessage(message);
      if (result && typeof result.catch === "function") result.catch(() => undefined);
    } catch {
      // FUSAA may be reloaded while WhatsApp remains open.
    }
  }

  function hasMainInterface() {
    return MAIN_INTERFACE_MARKERS.some(selector => document.querySelector(selector));
  }

  function unreadMarkerCount() {
    const nodes = new Set();
    for (const selector of UNREAD_MARKERS) {
      document.querySelectorAll(selector).forEach(node => nodes.add(node));
    }
    return nodes.size;
  }

  function titleUnreadCount() {
    // Only a leading numeric count is used momentarily; the title itself is never retained or sent.
    const matched = /^\((\d{1,3})\)\s/.exec(document.title);
    return matched ? Math.min(Number(matched[1]), 999) : 0;
  }

  function unreadLevel() {
    return Math.max(unreadMarkerCount(), titleUnreadCount());
  }

  function reportPageStatus() {
    send({ type: "FUSAA_PAGE_STATUS", pageReady: hasMainInterface() });
  }

  function emit(kind, count) {
    const now = Date.now();
    if (now - lastEventAt < EVENT_DEDUPLICATION_MS) return;
    lastEventAt = now;
    send({
      type: "FUSAA_WHATSAPP_EVENT",
      eventId: globalThis.crypto?.randomUUID ? globalThis.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      kind,
      count: Math.max(1, Math.min(999, Number.isInteger(count) ? count : 1))
    });
  }

  function updateReadiness() {
    const nextReady = hasMainInterface();
    if (nextReady !== pageReady) {
      pageReady = nextReady;
      reportPageStatus();
      if (pageReady) {
        lastUnreadLevel = unreadLevel();
        stabilizeUntil = Date.now() + STABILIZATION_DELAY_MS;
      }
    }
    return pageReady;
  }

  function inspectUnread() {
    if (!updateReadiness()) return;
    const nextUnreadLevel = unreadLevel();
    const increasedBy = nextUnreadLevel - lastUnreadLevel;
    lastUnreadLevel = nextUnreadLevel;
    if (Date.now() >= stabilizeUntil && increasedBy > 0) emit("UNREAD", increasedBy);
  }

  function nodeContainsIncomingMessage(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) return 0;
    let count = node.matches(INCOMING_MESSAGE_MARKERS) ? 1 : 0;
    count += node.querySelectorAll(INCOMING_MESSAGE_MARKERS).length;
    return count;
  }

  function flushIncomingCandidates() {
    incomingTimer = null;
    const count = incomingCandidates;
    incomingCandidates = 0;
    if (!pageReady || Date.now() < stabilizeUntil) return;
    // A navigation generally adds many old bubbles at once; ignore those batches.
    if (count > 0 && count <= 3) emit("MESSAGE", count);
  }

  function observeMutations(mutations) {
    let incoming = 0;
    for (const mutation of mutations) {
      if (mutation.type === "childList") {
        mutation.addedNodes.forEach(node => { incoming += nodeContainsIncomingMessage(node); });
      }
    }
    if (incoming > 0) {
      incomingCandidates += incoming;
      clearTimeout(incomingTimer);
      incomingTimer = setTimeout(flushIncomingCandidates, INCOMING_BATCH_DELAY_MS);
    }
    clearTimeout(checkTimer);
    checkTimer = setTimeout(inspectUnread, CHECK_DELAY_MS);
  }

  const observer = new MutationObserver(observeMutations);
  observer.observe(document.documentElement, { childList: true, subtree: true, characterData: true });

  document.addEventListener("visibilitychange", reportPageStatus, { passive: true });
  window.addEventListener("focus", reportPageStatus, { passive: true });
  window.addEventListener("beforeunload", () => send({ type: "FUSAA_PAGE_STATUS", pageReady: false }), { once: true });

  inspectUnread();
  reportPageStatus();
  window.setInterval(() => {
    reportPageStatus();
    inspectUnread();
  }, 25_000);
})();
