import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss()],
  build: {
    manifest: true,
    outDir: "static/dist",
    emptyOutDir: true,
    rollupOptions: {
      input: "frontend/shared/bootstrap.ts",
      output: {
        entryFileNames: "assets/app.js",
        assetFileNames: "assets/app.[ext]",
      },
    },
  },
});
