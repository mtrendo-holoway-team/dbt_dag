import "htmx.org";
import htmx from "htmx.org";

const updatingOpacity = "0.8";

document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const filterButton = target.closest("button[data-filter]") as HTMLButtonElement | null;
  if (!filterButton) return;
  document.dispatchEvent(
    new CustomEvent("dbt-dag-filter", { detail: { mode: filterButton.dataset.filter } })
  );
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

export function refreshInspectorMetadataBlocks(): void {
  const inspector = document.getElementById("inspector");
  if (!inspector) return;

  const refreshableBlocks = inspector.querySelectorAll<HTMLElement>('[data-inspector-refresh="metadata"]');
  refreshableBlocks.forEach((block) => {
    const url = block.getAttribute("hx-get");
    if (!url || !block.id) return;
    htmx.ajax("GET", url, { target: `#${block.id}`, swap: "outerHTML" });
  });
}
