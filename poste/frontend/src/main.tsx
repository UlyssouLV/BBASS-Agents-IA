import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "@/App";
import { PageInspecteur } from "@/screens/PageInspecteur";

import "./index.css";

// Cette application reste ouverte toute la journée (poste de travail) :
// sans staleTime, chaque changement d'onglet ou retour de focus fenêtre
// redéclenche un fetch réseau même quand rien n'a changé côté serveur.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
    },
  },
});

// Mode développeur (spec 1.3.0) : /inspecteur est un point d'entrée séparé
// de l'application principale, servi par le même build (poste main.py),
// ouvert dans un nouvel onglet par Ctrl+Maj+D (voir App.tsx).
const estInspecteur = globalThis.location.pathname === "/inspecteur";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {estInspecteur ? <PageInspecteur /> : <App />}
    </QueryClientProvider>
  </StrictMode>
);
