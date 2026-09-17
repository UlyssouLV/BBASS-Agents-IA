import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Le poste sert le front depuis poste/src/poste/static/ (FastAPI
// StaticFiles/FileResponse, voir main.py) : outDir écrit directement à cet
// endroit pour que main.py n'ait rien à changer, et le dossier généré est
// committé dans git (aucune étape de build sur le poste en production, voir
// ADR-0010).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  base: "/static/",
  build: {
    outDir: path.resolve(__dirname, "../src/poste/static"),
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "^/(connexion|deconnexion|mot-de-passe|compte|conversations|pieces-jointes|profil-travail|comptes|consommation)":
        {
          target: "http://127.0.0.1:8100",
          changeOrigin: true,
        },
    },
  },
});
