import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";

// Issue #272 (spec 1.6.3, point 10) : pendant la frappe, la réponse s'affiche
// déjà mise en forme. Chaque état du fil est relevé pendant l'animation ; aucun
// ne doit laisser voir une balise Markdown brute ou une syntaxe incomplète.

const COMPTE = {
  identifiant: "alice",
  prenom: "Alice",
  nom: "Martin",
  agence: "Castries",
  poles: [],
  est_admin: false,
  doit_changer_mot_de_passe: false,
};

const REPONSE_COMPLETE = [
  "## Synthèse",
  "",
  "Le **devis Dupont** est validé, voir [la fiche](https://exemple.fr/fiche).",
  "",
  "- **Montant** : 1 200 €",
  "- Délai : *deux semaines*",
  "",
  "| Poste | Montant |",
  "|---|---|",
  "| Main-d'œuvre | 800 € |",
  "| Fournitures | 400 € |",
  "",
  "```python",
  "total = 800 + 400",
  "```",
  "",
  "Fin.",
].join("\n");

const MESSAGE_ENREGISTRE = { tokens_contexte: null, fenetre_contexte: 0, date_creation: "2026-10-28T10:00:00Z" };

let reponseDeLaVm: string;

function reponseJson(corps: unknown, status = 200): Response {
  return new Response(JSON.stringify(corps), { status, headers: { "Content-Type": "application/json" } });
}

function jamais(): Promise<Response> {
  return new Promise(() => {});
}

function posteSimule(entree: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const chemin = typeof entree === "string" ? entree : entree.toString();
  const methode = init?.method ?? "GET";

  // Session déjà ouverte sur le poste : l'application arrive sur l'écran Compte.
  if (chemin === "/compte") {
    return Promise.resolve(reponseJson(COMPTE));
  }
  if (chemin === "/conversations" && methode === "POST") {
    const fin = { conversation: { id: 1, titre: "Devis" }, reponse: reponseDeLaVm, tokens_contexte: null, fenetre_contexte: 0 };
    return Promise.resolve(
      new Response(`event: fin\ndata: ${JSON.stringify(fin)}\n\n`, {
        headers: { "Content-Type": "text/event-stream" },
      })
    );
  }
  if (chemin === "/conversations") {
    return Promise.resolve(
      reponseJson([{ id: 2, titre: "Ancien devis", date_derniere_activite: "2026-10-28T10:00:00Z" }])
    );
  }
  if (chemin.startsWith("/conversations/2")) {
    return Promise.resolve(
      reponseJson({
        id: 2,
        titre: "Ancien devis",
        date_creation: "2026-10-28T10:00:00Z",
        date_derniere_activite: "2026-10-28T10:00:00Z",
        a_des_messages_plus_anciens: false,
        messages: [
          { id: 10, role: "user", contenu: "Bonjour", ...MESSAGE_ENREGISTRE },
          { id: 11, role: "assistant", contenu: REPONSE_COMPLETE, ...MESSAGE_ENREGISTRE },
        ],
      })
    );
  }
  // La conversation créée reste en chargement : le fil garde la réponse animée.
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

// Envoie un premier message et relève le texte de la bulle de réponse à
// chaque changement du fil, jusqu'à la fin de la frappe. Rend la bulle finale.
async function envoyerEtReleverLaFrappe(reponse: string): Promise<{ etats: string[]; bulle: Element }> {
  reponseDeLaVm = reponse;
  rendreApp();

  const champ = await screen.findByLabelText("Premier message");
  fireEvent.change(champ, { target: { value: "Bonjour" } });
  fireEvent.keyDown(champ, { key: "Enter" });

  const fil = await screen.findByRole("log");
  const etats: string[] = [];
  const observateur = new MutationObserver(() => etats.push(fil.lastElementChild?.textContent ?? ""));
  observateur.observe(fil, { childList: true, subtree: true, characterData: true });

  await waitFor(() => expect(fil.textContent).not.toContain("Réflexion"));
  // Fin de la frappe : plus aucun changement du fil pendant dix étapes.
  let nombreEtats: number;
  do {
    nombreEtats = etats.length;
    await new Promise((resolve) => setTimeout(resolve, 200));
  } while (etats.length !== nombreEtats);
  observateur.disconnect();
  return { etats, bulle: fil.lastElementChild as Element };
}

const MARQUEURS_BRUTS = ["**", "#", "|", "```", "[", "](", "*"];

function marqueursVisibles(etat: string): string[] {
  return MARQUEURS_BRUTS.filter((marqueur) => etat.includes(marqueur));
}

// Un nœud réutilisé d'une étape à l'autre garde un `style=""` vide quand son
// style est retiré : sans effet sur l'affichage.
function sansStyleVide(html: string): string {
  return html.replaceAll(' style=""', "");
}

describe("réponse mise en forme pendant la frappe", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(posteSimule));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("aucune balise Markdown brute n'est affichée à aucune étape de la frappe", async () => {
    const { etats } = await envoyerEtReleverLaFrappe(REPONSE_COMPLETE);

    expect(etats.length).toBeGreaterThan(10);
    expect(etats.filter((etat) => marqueursVisibles(etat).length > 0)).toEqual([]);
  });

  // Réponses courtes (au plus 60 caractères) : la frappe révèle un caractère
  // par étape, donc chaque coupure possible de la syntaxe est affichée.
  it.each([
    ["gras et lien", "**Oui**, voir [la fiche](https://ex.fr/a) ici."],
    ["tableau", "Voici :\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nFin"],
    ["bloc de code", "Code :\n\n```py\nx = 1\n```\n\nFin"],
    ["titre et liste", "# Titre\n\n- *un*\n- __deux__\n\nFin"],
  ])("%s coupé à chaque caractère ne s'affiche jamais cassé", async (_nom, reponse) => {
    const { etats } = await envoyerEtReleverLaFrappe(reponse);

    expect(etats.filter((etat) => marqueursVisibles(etat).length > 0 || etat.includes("_"))).toEqual([]);
  });

  it("le rendu final est celui d'une réponse enregistrée", async () => {
    const { bulle } = await envoyerEtReleverLaFrappe(REPONSE_COMPLETE);
    const renduFinal = sansStyleVide(bulle.innerHTML);

    fireEvent.click(await screen.findByText("Ancien devis"));
    const fil = await screen.findByRole("log");
    await waitFor(() => expect(fil.children.length).toBe(2));

    expect(sansStyleVide(fil.lastElementChild?.innerHTML ?? "")).toBe(renduFinal);
  });
});
