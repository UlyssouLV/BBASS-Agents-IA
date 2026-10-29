import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Assistant d'installation du Setup (spec 1.6.2, point 8) : embarqué dans
// BBASS.exe avec l'écran de démarrage (lanceur/ecran/, frontendDist de
// tauri.conf.json). Comme poste/src/poste/static (ADR-0010), le build est
// committé : cargo build du Lanceur n'a pas besoin de Node.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  base: "./",
  // Les favicons du poste ne servent pas dans la fenêtre du Setup.
  publicDir: false,
  build: {
    outDir: path.resolve(__dirname, "../../lanceur/ecran/installateur"),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, "installateur.html"),
    },
  },
});
