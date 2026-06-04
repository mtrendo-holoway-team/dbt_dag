type SearchResult = {
  id: string;
  label: string;
  type: string;
};

const overlay = document.getElementById("graph-search-overlay") as HTMLDivElement | null;
const input = document.getElementById("graph-search-input") as HTMLInputElement | null;
const popup = document.getElementById("graph-search-popup") as HTMLDivElement | null;

let results: SearchResult[] = [];
let activeIndex = 0;
let requestVersion = 0;

document.addEventListener(
  "keydown",
  (event) => {
    if (!overlay || !input || !popup) return;

    if (event.key === "/" && shouldOpenSearch(event)) {
      event.preventDefault();
      event.stopPropagation();
      openSearch();
      return;
    }

    if (!isSearchOpen()) return;

    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      closeSearch();
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      moveActiveIndex(1);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      moveActiveIndex(-1);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      selectActiveResult();
    }
  },
  true
);

overlay?.addEventListener("click", (event) => {
  if (event.target !== overlay) return;
  closeSearch();
});

input?.addEventListener("input", () => {
  void fetchResults(input.value.trim());
});

popup?.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const button = target.closest("button[data-node-id]") as HTMLButtonElement | null;
  if (!button) return;
  const nodeId = button.dataset.nodeId ?? "";
  if (!nodeId) return;
  if (window.dbtDagFocusNode) {
    window.dbtDagFocusNode(nodeId);
  } else {
    window.dbtDagSelectNode?.(nodeId);
  }
  closeSearch();
});

function shouldOpenSearch(event: KeyboardEvent): boolean {
  if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return false;
  const target = event.target as HTMLElement | null;
  if (!target) return true;
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return false;
  return !target.isContentEditable;
}

function isSearchOpen(): boolean {
  return overlay?.classList.contains("hidden") === false;
}

function openSearch(): void {
  if (!overlay || !input) return;
  overlay.classList.remove("hidden");
  overlay.classList.add("flex");
  input.value = "";
  results = [];
  activeIndex = 0;
  renderResults();
  window.setTimeout(() => input.focus(), 0);
}

function closeSearch(): void {
  if (!overlay || !input) return;
  overlay.classList.add("hidden");
  overlay.classList.remove("flex");
  input.blur();
  input.value = "";
  results = [];
  activeIndex = 0;
  renderResults();
}

async function fetchResults(query: string): Promise<void> {
  if (!popup) return;
  const currentRequest = (requestVersion += 1);
  if (!query) {
    results = [];
    activeIndex = 0;
    renderResults();
    return;
  }

  const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
  const nextResults = (await response.json()) as SearchResult[];
  if (currentRequest !== requestVersion) return;
  results = nextResults;
  activeIndex = 0;
  renderResults();
}

function moveActiveIndex(offset: number): void {
  if (results.length === 0) return;
  activeIndex = (activeIndex + offset + results.length) % results.length;
  renderResults();
}

function selectActiveResult(): void {
  const result = results[activeIndex];
  if (!result) return;
  if (window.dbtDagFocusNode) {
    window.dbtDagFocusNode(result.id);
  } else {
    window.dbtDagSelectNode?.(result.id);
  }
  closeSearch();
}

function renderResults(): void {
  if (!popup) return;
  if (results.length === 0) {
    popup.innerHTML =
      '<div class="px-4 py-6 text-sm text-zinc-500">Start typing to search the graph.</div>';
    return;
  }

  popup.innerHTML = results
    .map((result, index) => {
      const isActive = index === activeIndex;
      const activeClass = isActive ? "bg-zinc-800 text-zinc-100" : "text-zinc-300";
      return `
        <button
          class="flex w-full items-center justify-between rounded-xl px-3 py-3 text-left text-sm ${activeClass}"
          data-node-id="${result.id}"
          type="button"
        >
          <span class="min-w-0 truncate font-medium">${result.label}</span>
          <span class="ml-4 shrink-0 text-xs uppercase tracking-[0.2em] text-zinc-500">${result.type}</span>
        </button>
      `;
    })
    .join("");
}
