import { useState } from "react";
import type { UseMutationResult } from "@tanstack/react-query";

import { BarreLaterale } from "@/components/BarreLaterale";
import type { Compte } from "@/hooks/useSession";
import { OngletChat } from "@/onglets/OngletChat";
import { PagePanelAdministration } from "@/screens/PagePanelAdministration";
import { PageProfil } from "@/screens/PageProfil";

interface EcranCompteProps {
  compte: Compte;
  deconnexion: UseMutationResult<void, Error, void>;
}

// Disposition façon ChatGPT (issue #74) : la sidebar (BarreLaterale) devient
// la structure permanente de l'écran Compte pour la conversation en cours,
// remplaçant l'ancienne navigation par onglets à plat et l'en-tête qui
// portait l'identité du compte et les boutons Profil/Panel
// d'administration (voir docs/specs/v1.2.1-identite-visuelle-disposition.md).
// Ces deux pages restent plein écran, sans sidebar, atteignables uniquement
// depuis la puce compte.
export function EcranCompte({ compte, deconnexion }: Readonly<EcranCompteProps>) {
  const [vue, setVue] = useState<"chat" | "profil" | "panel-administration">("chat");
  const [conversationOuverteId, setConversationOuverteId] = useState<number | null>(null);
  // Issue #83 : id de la conversation qui vient d'être créée, tant que son
  // titre n'a pas fini de s'écrire dans la sidebar (voir
  // BarreLaterale.tsx — TitreAnimeConversation). Distinct de
  // conversationOuverteId, qui reste positionné après la fin de
  // l'animation (l'utilisateur continue de discuter dans ce fil).
  const [conversationRecenteId, setConversationRecenteId] = useState<number | null>(null);

  function gererConversationCreee(id: number) {
    setConversationOuverteId(id);
    setConversationRecenteId(id);
  }

  if (vue === "profil") {
    return <PageProfil deconnexion={deconnexion} onRetour={() => setVue("chat")} />;
  }

  // Le bouton qui positionne cette vue n'est déjà rendu que pour un compte
  // administrateur (voir BarreLaterale.tsx), mais on revérifie ici
  // `compte.est_admin` pour que le rendu de la page reste conforme à «
  // accessible uniquement si compte.est_admin » (docs/specs/v1.2.1-
  // identite-visuelle-disposition.md) même si `vue` venait à être positionné
  // autrement à l'avenir.
  if (vue === "panel-administration" && compte.est_admin) {
    return <PagePanelAdministration onRetour={() => setVue("chat")} />;
  }

  return (
    <div className="flex h-screen">
      <BarreLaterale
        compte={compte}
        conversationOuverteId={conversationOuverteId}
        onSelectionnerConversation={setConversationOuverteId}
        onOuvrirProfil={() => setVue("profil")}
        onOuvrirPanelAdministration={() => setVue("panel-administration")}
        conversationRecenteId={conversationRecenteId}
        onAnimationTitreTerminee={() => setConversationRecenteId(null)}
      />

      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden px-6 py-8">
        {compte.avertissement && (
          <p role="alert" className="mb-4 text-sm text-destructive">
            {compte.avertissement}
          </p>
        )}

        <OngletChat conversationOuverteId={conversationOuverteId} onConversationCreee={gererConversationCreee} />
      </main>
    </div>
  );
}
