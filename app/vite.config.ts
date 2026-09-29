import { defineConfig } from "vite";

export default defineConfig({
  build: {
    manifest: true,
    outDir: "static/dist",
    emptyOutDir: true,
    rollupOptions: { input: "frontend/shared/bootstrap.ts" },
  },
});
