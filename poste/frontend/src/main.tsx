import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "@/App";

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

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
