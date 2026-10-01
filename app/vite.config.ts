import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => ({
  plugins: mode === "wip" ? [tailwindcss()] : [],
  build: {
    manifest: true,
    outDir: mode === "wip" ? "static/dist/wip" : "static/dist",
    emptyOutDir: true,
    rollupOptions: {
      input:
        mode === "wip"
          ? "frontend/wip-preview.ts"
          : "frontend/shared/bootstrap.ts",
      output: {
        entryFileNames: "assets/app.js",
        assetFileNames: "assets/app.[ext]",
      },
    },
  },
}));
