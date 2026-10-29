import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";

// Issue #268 (spec 1.6.3, point 1) : le compte qui se connecte après un autre
// sur le même poste ne voit rien du précédent, même un instant. La liste de
// conversations de B ne répond jamais ici : tout ce que la barre latérale
// afficherait viendrait du cache laissé par A.

const COMPTES = {
  alice: { identifiant: "alice", prenom: "Alice", nom: "Martin", agence: "Castries", poles: [], est_admin: false, doit_changer_mot_de_passe: false },
  bruno: { identifiant: "bruno", prenom: "Bruno", nom: "Durand", agence: "Castries", poles: [], est_admin: false, doit_changer_mot_de_passe: false },
} as const;

type Identifiant = keyof typeof COMPTES;

let compteConnecte: Identifiant | null;
let jetonRevoque: boolean;

function reponseJson(corps: unknown, status = 200): Response {
  return new Response(JSON.stringify(corps), { status, headers: { "Content-Type": "application/json" } });
}

function jamais(): Promise<Response> {
  return new Promise(() => {});
}

function posteSimule(entree: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const chemin = typeof entree === "string" ? entree : entree.toString();
  const methode = init?.method ?? "GET";

  if (chemin === "/connexion" && methode === "POST") {
    const { identifiant } = JSON.parse(String(init?.body)) as { identifiant: Identifiant };
    compteConnecte = identifiant;
    jetonRevoque = false;
    return Promise.resolve(reponseJson(COMPTES[identifiant]));
  }
  if (chemin === "/deconnexion" && methode === "POST") {
    compteConnecte = null;
    return Promise.resolve(new Response(null, { status: 204 }));
  }
  if (compteConnecte === null || jetonRevoque) {
    return Promise.resolve(reponseJson({ detail: "Session expirée." }, 401));
  }
  if (chemin === "/compte") {
    return Promise.resolve(reponseJson(COMPTES[compteConnecte]));
  }
  if (chemin === "/conversations" && compteConnecte === "alice") {
    return Promise.resolve(
      reponseJson([{ id: 1, titre: "Devis secret d'Alice", date_derniere_activite: "2026-10-28T10:00:00Z" }])
    );
  }
  if (chemin === "/profil-travail" && compteConnecte === "alice") {
    return Promise.resolve(reponseJson({ contenu: "Alice suit le dossier Dupont.", date_derniere_maj: null }));
  }
  // Le reste (dont la liste et le profil de B) reste en chargement.
  return jamais();
}

function rendreApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

async function seConnecter(identifiant: Identifiant) {
  fireEvent.change(await screen.findByLabelText("Identifiant"), { target: { value: identifiant } });
  fireEvent.change(screen.getByLabelText("Mot de passe"), { target: { value: "secret" } });
  fireEvent.click(screen.getByRole("button", { name: "Connexion" }));
  await screen.findByText(`${COMPTES[identifiant].prenom} ${COMPTES[identifiant].nom}`);
}

describe("changement de compte sur le même poste", () => {
  beforeEach(() => {
    compteConnecte = null;
    jetonRevoque = false;
    vi.stubGlobal("fetch", vi.fn(posteSimule));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("après une déconnexion, le compte suivant ne voit aucune conversation du précédent", async () => {
    rendreApp();
    await seConnecter("alice");
    await screen.findByText("Devis secret d'Alice");

    fireEvent.click(screen.getByRole("button", { name: "Profil" }));
    fireEvent.click(await screen.findByRole("button", { name: "Se déconnecter" }));

    await seConnecter("bruno");
    expect(screen.queryByText("Devis secret d'Alice")).toBeNull();
  });

  it("après une déconnexion forcée, le compte suivant ne voit aucune conversation du précédent", async () => {
    rendreApp();
    await seConnecter("alice");
    await screen.findByText("Devis secret d'Alice");

    // Jeton révoqué côté poste : le prochain appel (ici l'ouverture du
    // profil) reçoit un 401 et l'application revient à l'écran de connexion.
    jetonRevoque = true;
    fireEvent.click(screen.getByRole("button", { name: "Profil" }));
    await waitFor(() => expect(screen.getByLabelText("Identifiant")).toBeTruthy());

    await seConnecter("bruno");
    expect(screen.queryByText("Devis secret d'Alice")).toBeNull();
  });

  it("après une déconnexion, le compte suivant ne voit pas le profil du précédent", async () => {
    rendreApp();
    await seConnecter("alice");

    fireEvent.click(screen.getByRole("button", { name: "Profil" }));
    await screen.findByText("Alice suit le dossier Dupont.");
    fireEvent.click(screen.getByRole("button", { name: "Se déconnecter" }));

    await seConnecter("bruno");
    fireEvent.click(screen.getByRole("button", { name: "Profil" }));
    await screen.findByRole("button", { name: "Se déconnecter" });
    expect(screen.queryByText("Alice suit le dossier Dupont.")).toBeNull();
  });
});
