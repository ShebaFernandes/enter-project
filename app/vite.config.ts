import { defineConfig } from "vite";

export default defineConfig({
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
