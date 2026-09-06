const $ = id => document.getElementById(id);

async function command(type) {
  const response = await chrome.runtime.sendMessage({ type });
  if (!response?.ok) throw new Error(response?.error || "L’extension ne répond pas.");
  return response.result;
}

function render(status, extra = "") {
  const state = $("state");
  const parts = [];
  let tone = "";
  if (!status.paired) {
    parts.push("Extension non associée.");
    tone = "warn";
  } else if (status.pageReady) {
    parts.push("Extension associée · WhatsApp Web est ouvert.");
  } else {
    parts.push("Extension associée · WhatsApp Web n’est pas détecté.");
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
}

async function refresh(extra = "") {
  try {
    render(await command("FUSAA_GET_STATUS"), extra);
  } catch (error) {
    render({ paired: false, pageReady: false, queuedEvents: 0, lastError: error.message });
  }
}

$("refresh").addEventListener("click", () => void refresh());
$("disconnect").addEventListener("click", async () => {
  try {
    render(await command("FUSAA_UNPAIR"), "Liaison supprimée de Brave.");
  } catch (error) {
    void refresh(error.message);
  }
});
void refresh();
