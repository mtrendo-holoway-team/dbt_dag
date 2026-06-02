import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [tailwindcss()],
  build: {
    manifest: true,
    outDir: "src/dbt_dag/web/static/dist",
    rollupOptions: {
      input: {
        graph: "src/dbt_dag/web/static/js/graph.ts",
        search: "src/dbt_dag/web/static/js/search.ts",
        inspectors: "src/dbt_dag/web/static/js/inspectors.ts",
        styles: "src/dbt_dag/web/static/css/tailwind.css"
      }
    }
  }
});
