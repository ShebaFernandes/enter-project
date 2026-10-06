import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => ({
  base: ["react", "showcase"].includes(mode) ? "./" : "/",
  plugins: ["wip", "react", "showcase"].includes(mode) ? [tailwindcss()] : [],
  build: {
    manifest: true,
    outDir: ["wip", "react", "showcase"].includes(mode)
      ? `static/dist/${mode}`
      : "static/dist",
    emptyOutDir: true,
    rollupOptions: {
      preserveEntrySignatures: "strict",
      input:
        mode === "wip"
          ? "frontend/wip-preview.ts"
          : mode === "react"
            ? "frontend/react/entry.ts"
            : mode === "showcase"
              ? "tests/browser/fixtures/fm2-showcase.tsx"
              : "frontend/shared/bootstrap.ts",
      output: {
        entryFileNames: "assets/app.js",
        assetFileNames: "assets/app.[ext]",
      },
    },
  },
}));
