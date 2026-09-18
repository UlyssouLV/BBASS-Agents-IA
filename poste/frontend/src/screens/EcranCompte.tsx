import { useState } from "react";
import type { UseMutationResult } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Compte } from "@/hooks/useSession";
import { OngletChat } from "@/onglets/OngletChat";
import { PagePanelAdministration } from "@/screens/PagePanelAdministration";
import { PageProfil } from "@/screens/PageProfil";

interface EcranCompteProps {
  compte: Compte;
  deconnexion: UseMutationResult<void, Error, void>;
}

export function EcranCompte({ compte, deconnexion }: Readonly<EcranCompteProps>) {
  const [onglet, setOnglet] = useState("chat");
  const [vue, setVue] = useState<"chat" | "profil" | "panel-administration">("chat");

  const poleAgence = [compte.poles.join(", "), compte.agence].filter(Boolean).join(" — ");

  if (vue === "profil") {
    return <PageProfil deconnexion={deconnexion} onRetour={() => setVue("chat")} />;
  }

  if (vue === "panel-administration") {
    return <PagePanelAdministration onRetour={() => setVue("chat")} />;
  }

  return (
    <main className="mx-auto mt-8 w-full max-w-4xl px-4">
      <header className="mb-4 flex items-center justify-between gap-4">
        <span className="text-sm">
          Connecté en tant que{" "}
          <strong className="font-medium">
            {compte.prenom} {compte.nom} ({compte.identifiant})
          </strong>{" "}
          ({poleAgence})
        </span>
        <div className="flex items-center gap-2">
          {compte.est_admin && (
            <Button variant="outline" onClick={() => setVue("panel-administration")}>
              Panel d'administration
            </Button>
          )}
          <Button variant="outline" onClick={() => setVue("profil")}>
            Profil
          </Button>
        </div>
      </header>

      {compte.avertissement && (
        <p role="alert" className="mb-4 text-sm text-destructive">
          {compte.avertissement}
        </p>
      )}

      <Tabs value={onglet} onValueChange={setOnglet}>
        <TabsList>
          <TabsTrigger value="chat">Discussion</TabsTrigger>
        </TabsList>
        <TabsContent value="chat">
          <OngletChat />
        </TabsContent>
      </Tabs>
    </main>
  );
}
