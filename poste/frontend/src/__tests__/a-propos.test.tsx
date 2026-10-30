import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";

// Issue #282 (spec 1.6.4, point 9) : le Lanceur ouvre désormais une adresse qui
// porte la version ; À propos doit toujours s'ouvrir après une vérification.

function reponseJson(corps: unknown, status = 200): Response {
  return new Response(JSON.stringify(corps), { status, headers: { "Content-Type": "application/json" } });
}

function posteSimule(entree: RequestInfo | URL): Promise<Response> {
  const chemin = typeof entree === "string" ? entree : entree.toString();

  if (chemin === "/a-propos") {
    return Promise.resolve(
      reponseJson({
        version_poste: "1.6.5",
        version_serveur: "1.6.5",
        derniere_verification: null,
        verification_possible: true,
      })
    );
  }
  if (chemin === "/compte") {
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

describe("adresse ouverte par le Lanceur", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(posteSimule));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    globalThis.history.replaceState(null, "", "/");
  });

  it("après une vérification, À propos s'ouvre et ne se rouvrira pas au rechargement", async () => {
    globalThis.history.replaceState(null, "", "/?a-propos&v=1.6.5");
    rendreApp();

    expect(await screen.findByRole("dialog", { name: "À propos de BBASS" })).toBeTruthy();
    expect(globalThis.location.search).toBe("?v=1.6.5");
  });

  it("sans vérification, la version dans l'adresse n'ouvre pas À propos", async () => {
    globalThis.history.replaceState(null, "", "/?v=1.6.5");
    rendreApp();

    await screen.findByLabelText(/identifiant/i);
    expect(screen.queryByRole("dialog", { name: "À propos de BBASS" })).toBeNull();
  });
});
