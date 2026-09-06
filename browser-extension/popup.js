const $ = id => document.getElementById(id);

async function command(type, payload = {}) {
  const response = await chrome.runtime.sendMessage({ type, ...payload });
  if (!response?.ok) throw new Error(response?.error || "L’extension ne répond pas.");
  return response.result;
}

function showState(status, extra = "") {
  const state = $("state");
  const parts = [];
  let tone = "";
  if (!status.paired) {
    parts.push("Non associée : créez un code dans FUSAA puis collez-le ici.");
    tone = "warn";
  } else if (status.pageReady) {
    parts.push("Associée · WhatsApp Web est détecté.");
  } else {
    parts.push("Associée · ouvrez WhatsApp Web dans Brave.");
    tone = "warn";
  }
  if (status.queuedEvents) parts.push(`${status.queuedEvents} alerte(s) en attente.`);
  if (extra) parts.push(extra);
  if (status.lastError) {
    parts.push(status.lastError);
    tone = "error";
  }
  state.className = `state ${tone}`.trim();
  state.textContent = parts.join(" ");
  $("disconnect").hidden = !status.paired;
}

async function refresh(extra = "") {
  try {
    showState(await command("FUSAA_GET_STATUS"), extra);
  } catch (error) {
    showState({ paired: false, pageReady: false, queuedEvents: 0, lastError: error.message });
  }
}

$("pairForm").addEventListener("submit", async event => {
  event.preventDefault();
  const button = $("pairButton");
  button.disabled = true;
  try {
    const status = await command("FUSAA_PAIR", { code: $("pairCode").value });
    $("pairCode").value = "";
    showState(status, "Liaison enregistrée sur ce PC.");
  } catch (error) {
    await refresh(error.message);
  } finally {
    button.disabled = false;
  }
});

$("disconnect").addEventListener("click", async () => {
  try {
    showState(await command("FUSAA_UNPAIR"), "Liaison supprimée de Brave.");
  } catch (error) {
    await refresh(error.message);
  }
});

$("options").addEventListener("click", () => chrome.runtime.openOptionsPage());
void refresh();
