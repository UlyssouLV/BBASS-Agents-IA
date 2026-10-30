import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";

// Issue #273 (spec 1.6.3, point 11) : le bandeau de mise à jour prend sa place
// en haut de la page au lieu de recouvrir le bouton « … ». Sans mise en page
// dans le DOM simulé, seule sa position fixe est observable ici.

const BANDEAU = "Mise à jour impossible : certaines fonctionnalités peuvent ne pas fonctionner.";
const COMPTE = { identifiant: "alice", prenom: "Alice", nom: "Martin", agence: "Castries", poles: [], est_admin: false, doit_changer_mot_de_passe: false };

type EtatSession = "deconnecte" | "connecte" | "serveur-injoignable";

let etatSession: EtatSession;

function reponseJson(corps: unknown, status = 200): Response {
  return new Response(JSON.stringify(corps), { status, headers: { "Content-Type": "application/json" } });
}

function posteSimule(entree: RequestInfo | URL): Promise<Response> {
  const chemin = typeof entree === "string" ? entree : entree.toString();

  if (chemin === "/mise-a-jour") {
    return Promise.resolve(reponseJson({ resultat: "echec", bandeau: BANDEAU }));
  }
  if (chemin === "/compte" && etatSession === "serveur-injoignable") {
    return Promise.resolve(reponseJson({ detail: "Serveur injoignable." }, 503));
  }
  if (chemin === "/compte" && etatSession === "connecte") {
    return Promise.resolve(reponseJson(COMPTE));
  }
  if (etatSession === "deconnecte") {
    return Promise.resolve(reponseJson({ detail: "Session expirée." }, 401));
  }
  // Le reste n'intéresse pas ces scénarios.
  return new Promise(() => {});
}

function rendreApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

async function ouvrirMenuOptions() {
  const bouton = await screen.findByRole("button", { name: "Plus d'options" });
  fireEvent.pointerDown(bouton, { button: 0, ctrlKey: false });
  await screen.findByRole("menuitem", { name: "Configuration" });
}

describe("bandeau de mise à jour", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(posteSimule));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("sur l'écran de connexion, il laisse le bouton « … » ouvrir son menu", async () => {
    etatSession = "deconnecte";
    rendreApp();

    expect((await screen.findByRole("alert")).textContent).toContain(BANDEAU);
    await ouvrirMenuOptions();
  });

  it("dans l'application connectée, il laisse le bouton « … » ouvrir son menu", async () => {
    etatSession = "connecte";
    rendreApp();

    await screen.findByRole("alert");
    fireEvent.click(await screen.findByRole("button", { name: "Profil" }));
    await ouvrirMenuOptions();
  });

  it("n'est plus posé par-dessus le contenu", async () => {
    etatSession = "deconnecte";
    rendreApp();

    expect((await screen.findByRole("alert")).className).not.toMatch(/\bfixed\b/);
  });

  it("une fois fermé, laisse le bouton « … » en place", async () => {
    etatSession = "deconnecte";
    rendreApp();

    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Fermer le bandeau" }));

    expect(screen.queryByRole("alert")).toBeNull();
    await ouvrirMenuOptions();
  });

  it("quand la session n'a pas pu être vérifiée, le bouton « … » ne se pose pas sur lui", async () => {
    etatSession = "serveur-injoignable";
    rendreApp();

    await screen.findByText(/Impossible de vérifier la session/);
    expect(screen.getByRole("button", { name: "Plus d'options" }).className).not.toMatch(/\bfixed\b/);
  });
});
