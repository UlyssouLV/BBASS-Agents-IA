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

  if (vue === "profil") {
    return <PageProfil deconnexion={deconnexion} onRetour={() => setVue("chat")} />;
  }

  if (vue === "panel-administration") {
    return <PagePanelAdministration onRetour={() => setVue("chat")} />;
  }

  return (
    <div className="flex">
      <BarreLaterale
        compte={compte}
        conversationOuverteId={conversationOuverteId}
        onSelectionnerConversation={setConversationOuverteId}
        onOuvrirProfil={() => setVue("profil")}
        onOuvrirPanelAdministration={() => setVue("panel-administration")}
      />

      <main className="min-w-0 flex-1 overflow-y-auto px-6 py-8">
        {compte.avertissement && (
          <p role="alert" className="mb-4 text-sm text-destructive">
            {compte.avertissement}
          </p>
        )}

        <OngletChat conversationOuverteId={conversationOuverteId} onConversationCreee={setConversationOuverteId} />
      </main>
    </div>
  );
}
