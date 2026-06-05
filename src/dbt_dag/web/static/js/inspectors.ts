import "htmx.org";
import htmx from "htmx.org";

const updatingOpacity = "0.8";
const closeDelayMs = 10_000;
const chordDelayMs = 900;

type CommandAction = "build" | "run" | "test" | "compile";

type StreamEvent = {
  event: "start" | "chunk" | "finish" | "error";
  action?: CommandAction;
  command?: string;
  compiled_sql?: string | null;
  exit_code?: number;
  message?: string;
  ok?: boolean;
  task_id?: number;
  text?: string;
};

type CommandPopup = {
  close: () => void;
  log: HTMLElement;
  setStatus: (value: string, tone?: "neutral" | "success" | "error") => void;
  title: HTMLElement;
};

let activeAbortController: AbortController | null = null;
let activePopup: CommandPopup | null = null;
let activeCloseTimer: number | null = null;
let pendingChord = "";
let pendingChordTimer: number | null = null;

document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const filterButton = target.closest("button[data-filter]") as HTMLButtonElement | null;
  if (filterButton) {
    document.dispatchEvent(
      new CustomEvent("dbt-dag-filter", { detail: { mode: filterButton.dataset.filter } })
    );
    return;
  }

  const actionButton = target.closest("button[data-command-action]") as HTMLButtonElement | null;
  if (!actionButton) return;
  void runCommandAction(actionButton);
});

document.body.addEventListener("htmx:beforeRequest", (event) => {
  const target = (event as CustomEvent).detail.target as HTMLElement | null;
  if (!target || !target.closest("#inspector")) return;
  target.style.opacity = updatingOpacity;
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  const target = (event as CustomEvent).detail.target as HTMLElement | null;
  if (!target || !target.closest("#inspector")) return;
  target.style.opacity = "";
});

document.body.addEventListener("htmx:responseError", (event) => {
  const target = (event as CustomEvent).detail.target as HTMLElement | null;
  if (!target || !target.closest("#inspector")) return;
  target.style.opacity = "";
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && activePopup) {
    event.preventDefault();
    closeActivePopup();
    return;
  }
  if (event.defaultPrevented || isTypingTarget(event.target)) {
    resetPendingChord();
    return;
  }
  const key = parseChordKey(event.key);
  if (!key) {
    resetPendingChord();
    return;
  }
  const nextChord = pendingChord ? `${pendingChord}${key}` : key;
  const actionButton = findActionButtonByShortcut(nextChord);
  if (pendingChord === "" && key !== "a") {
    return;
  }
  if (pendingChord === "" && key === "a") {
    pendingChord = key;
    schedulePendingChordReset();
    event.preventDefault();
    return;
  }
  if (!actionButton) {
    resetPendingChord();
    return;
  }
  resetPendingChord();
  event.preventDefault();
  void runCommandAction(actionButton);
});

export function refreshInspectorMetadataBlocks(): void {
  refreshInspectorBlocks("metadata");
}

function refreshInspectorTaskBlocks(): void {
  refreshInspectorBlocks("tasks");
}

function refreshInspectorBlocks(refreshType: string): void {
  const inspector = document.getElementById("inspector");
  if (!inspector) return;

  const refreshableBlocks = inspector.querySelectorAll<HTMLElement>(
    `[data-inspector-refresh="${refreshType}"]`
  );
  refreshableBlocks.forEach((block) => {
    const url = block.getAttribute("hx-get");
    if (!url || !block.id) return;
    htmx.ajax("GET", url, { target: `#${block.id}`, swap: "outerHTML" });
  });
}

async function runCommandAction(button: HTMLButtonElement): Promise<void> {
  const url = button.dataset.commandUrl;
  const action = button.dataset.commandAction as CommandAction | undefined;
  const label = button.dataset.commandLabel;
  if (!url || !action || !label) return;

  closeActivePopup();
  const popup = createCommandPopup(label, action);
  activePopup = popup;
  popup.setStatus("Running");
  popup.log.textContent = "";
  appendLogLine(popup.log, `$ ${label.toLowerCase()}`);

  const abortController = new AbortController();
  activeAbortController = abortController;

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/x-ndjson" },
      signal: abortController.signal,
    });
    if (!response.ok || !response.body) {
      popup.setStatus("Failed", "error");
      showCommandAlert("Could not start dbt action.", "error");
      return;
    }
    await consumeCommandStream(response.body, popup, action);
  } catch (error) {
    if (abortController.signal.aborted) {
      return;
    }
    popup.setStatus("Failed", "error");
    appendLogLine(
      popup.log,
      error instanceof Error ? error.message : "Command stream failed unexpectedly."
    );
    showCommandAlert("Command stream failed.", "error");
  } finally {
    if (activeAbortController === abortController) {
      activeAbortController = null;
    }
  }
}

async function consumeCommandStream(
  stream: ReadableStream<Uint8Array>,
  popup: CommandPopup,
  action: CommandAction
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      handleStreamEvent(JSON.parse(line) as StreamEvent, popup, action);
    }
  }

  if (buffer.trim()) {
    handleStreamEvent(JSON.parse(buffer) as StreamEvent, popup, action);
  }
}

function handleStreamEvent(
  event: StreamEvent,
  popup: CommandPopup,
  action: CommandAction
): void | Promise<void> {
  if (event.event === "start") {
    if (event.command) {
      popup.title.textContent = event.command;
      popup.log.textContent = "";
      appendLogLine(popup.log, `$ ${event.command}`);
    }
    return;
  }
  if (event.event === "chunk") {
    if (event.text) {
      appendLogText(popup.log, event.text);
    }
    return;
  }
  if (event.event === "error") {
    popup.setStatus("Failed", "error");
    appendLogLine(popup.log, event.message ?? "Command failed.");
    return;
  }
  if (event.event !== "finish") {
    return;
  }

  refreshInspectorTaskBlocks();
  const ok = event.ok === true;
  popup.setStatus(ok ? "Succeeded" : "Failed", ok ? "success" : "error");
  if (!ok) {
    return;
  }

  if (action === "compile") {
    if (event.compiled_sql) {
      void copyCompiledSql(event.compiled_sql);
    } else {
      showCommandAlert("Compiled SQL was not found.", "error");
    }
    closeActivePopup();
    return;
  }

  refreshInspectorMetadataBlocks();
  appendLogLine(popup.log, `\nCommand finished successfully. Closing in 10s.`);
  if (activeCloseTimer !== null) {
    window.clearTimeout(activeCloseTimer);
  }
  activeCloseTimer = window.setTimeout(() => {
    closeActivePopup();
  }, closeDelayMs);
}

async function copyCompiledSql(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    showCommandAlert("Compiled SQL copied to clipboard.", "success");
  } catch (error) {
    showCommandAlert("Could not copy compiled SQL to clipboard.", "error");
    if (activePopup) {
      appendLogLine(
        activePopup.log,
        error instanceof Error ? error.message : "Clipboard copy failed."
      );
    }
  }
}

function createCommandPopup(label: string, action: CommandAction): CommandPopup {
  const overlay = document.createElement("div");
  overlay.className =
    "fixed inset-0 z-50 flex items-center justify-center bg-zinc-950/70 p-4 backdrop-blur-sm";

  const panel = document.createElement("section");
  panel.className =
    "flex max-h-[85vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-zinc-700 bg-zinc-950 shadow-2xl";

  const header = document.createElement("header");
  header.className = "flex items-center justify-between gap-4 border-b border-zinc-800 px-5 py-4";

  const titleWrap = document.createElement("div");
  titleWrap.className = "space-y-1";

  const heading = document.createElement("h2");
  heading.className = "text-base font-semibold text-zinc-100";
  heading.textContent = `${label} output`;

  const subtitle = document.createElement("p");
  subtitle.className = "font-mono text-xs text-zinc-500";
  subtitle.textContent = action;

  titleWrap.append(heading, subtitle);

  const actions = document.createElement("div");
  actions.className = "flex items-center gap-3";

  const status = document.createElement("span");
  status.className = "rounded-full border border-zinc-700 px-3 py-1 text-xs text-zinc-300";
  status.textContent = "Pending";

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "rounded-md border border-zinc-700 px-3 py-1 text-sm text-zinc-300";
  closeButton.textContent = "Close";
  closeButton.addEventListener("click", () => {
    closeActivePopup();
  });

  actions.append(status, closeButton);
  header.append(titleWrap, actions);

  const log = document.createElement("pre");
  log.className =
    "min-h-[320px] overflow-auto bg-zinc-950 px-5 py-4 font-mono text-xs leading-6 text-zinc-200";
  log.textContent = "";

  panel.append(header, log);
  overlay.append(panel);
  document.body.append(overlay);

  return {
    close: () => {
      overlay.remove();
    },
    log,
    setStatus: (value: string, tone: "neutral" | "success" | "error" = "neutral") => {
      status.textContent = value;
      status.className = `rounded-full border px-3 py-1 text-xs ${
        tone === "success"
          ? "border-emerald-500/40 text-emerald-300"
          : tone === "error"
            ? "border-rose-500/40 text-rose-300"
            : "border-zinc-700 text-zinc-300"
      }`;
    },
    title: subtitle,
  };
}

function closeActivePopup(): void {
  if (activeAbortController) {
    activeAbortController.abort();
    activeAbortController = null;
  }
  if (activeCloseTimer !== null) {
    window.clearTimeout(activeCloseTimer);
    activeCloseTimer = null;
  }
  activePopup?.close();
  activePopup = null;
}

function showCommandAlert(message: string, tone: "success" | "error"): void {
  const container = ensureAlertContainer();
  const alert = document.createElement("div");
  alert.className =
    "rounded-xl border px-4 py-3 text-sm shadow-lg transition-opacity " +
    (tone === "success"
      ? "border-emerald-500/40 bg-emerald-950/90 text-emerald-100"
      : "border-rose-500/40 bg-rose-950/90 text-rose-100");
  alert.textContent = message;
  container.append(alert);
  window.setTimeout(() => {
    alert.style.opacity = "0";
    window.setTimeout(() => {
      alert.remove();
    }, 200);
  }, 2500);
}

function ensureAlertContainer(): HTMLElement {
  const existing = document.getElementById("inspector-alerts");
  if (existing) {
    return existing;
  }
  const container = document.createElement("div");
  container.id = "inspector-alerts";
  container.className = "fixed right-4 top-4 z-[60] flex max-w-sm flex-col gap-2";
  document.body.append(container);
  return container;
}

function appendLogLine(log: HTMLElement, line: string): void {
  appendLogText(log, `${line}\n`);
}

function appendLogText(log: HTMLElement, text: string): void {
  log.textContent += text;
  log.scrollTop = log.scrollHeight;
}

function findActionButtonByShortcut(shortcut: string): HTMLButtonElement | null {
  const actionsBlock = document.querySelector<HTMLElement>('#inspector [data-node-type="model"]');
  if (!actionsBlock) return null;
  return actionsBlock.querySelector<HTMLButtonElement>(
    `button[data-command-shortcut="${shortcut}"]`
  );
}

function parseChordKey(key: string): string | null {
  return /^[a-z]$/i.test(key) ? key.toLowerCase() : null;
}

function schedulePendingChordReset(): void {
  if (pendingChordTimer !== null) {
    window.clearTimeout(pendingChordTimer);
  }
  pendingChordTimer = window.setTimeout(() => {
    resetPendingChord();
  }, chordDelayMs);
}

function resetPendingChord(): void {
  pendingChord = "";
  if (pendingChordTimer !== null) {
    window.clearTimeout(pendingChordTimer);
    pendingChordTimer = null;
  }
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target.isContentEditable
  );
}
