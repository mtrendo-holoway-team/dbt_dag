type SearchResult = {
  id: string;
  label: string;
  type: string;
};

const input = document.getElementById("graph-search") as HTMLInputElement | null;
const popup = document.getElementById("search-popup");

input?.addEventListener("input", async () => {
  if (!popup || !input.value.startsWith("/")) {
    popup?.classList.add("hidden");
    return;
  }
  const response = await fetch(`/search?q=${encodeURIComponent(input.value)}`);
  const results = (await response.json()) as SearchResult[];
  popup.innerHTML = results
    .map(
      (result) => `<button class="block w-full px-3 py-2 text-left text-sm hover:bg-zinc-800" data-node-id="${result.id}">
        <span class="font-medium">${result.label}</span>
        <span class="ml-2 text-xs text-zinc-500">${result.type}</span>
      </button>`
    )
    .join("");
  popup.classList.toggle("hidden", results.length === 0);
});

popup?.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const button = target.closest("button[data-node-id]") as HTMLButtonElement | null;
  if (!button) return;
  window.dbtDagSelectNode?.(button.dataset.nodeId ?? "");
  popup.classList.add("hidden");
});

input?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || !popup) return;
  const first = popup.querySelector("button[data-node-id]") as HTMLButtonElement | null;
  if (!first) return;
  window.dbtDagSelectNode?.(first.dataset.nodeId ?? "");
  popup.classList.add("hidden");
});
