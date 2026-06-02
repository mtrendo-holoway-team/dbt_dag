import "htmx.org";

document.addEventListener("click", (event) => {
  const target = event.target as HTMLElement;
  const filterButton = target.closest("button[data-filter]") as HTMLButtonElement | null;
  if (!filterButton) return;
  document.dispatchEvent(
    new CustomEvent("dbt-dag-filter", { detail: { mode: filterButton.dataset.filter } })
  );
});
