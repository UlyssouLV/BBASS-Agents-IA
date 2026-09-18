import { useState } from "react";
import type { UseMutationResult } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Compte } from "@/hooks/useSession";
import { OngletChat } from "@/onglets/OngletChat";
import { OngletComptes } from "@/onglets/OngletComptes";
import { OngletConsommations } from "@/onglets/OngletConsommations";
import { PageProfil } from "@/screens/PageProfil";

interface EcranCompteProps {
  compte: Compte;
  deconnexion: UseMutationResult<void, Error, void>;
}

export function EcranCompte({ compte, deconnexion }: Readonly<EcranCompteProps>) {
  const [onglet, setOnglet] = useState("chat");
  const [vue, setVue] = useState<"chat" | "profil">("chat");

  const poleAgence = [compte.poles.join(", "), compte.agence].filter(Boolean).join(" — ");

  if (vue === "profil") {
    return <PageProfil deconnexion={deconnexion} onRetour={() => setVue("chat")} />;
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
        <Button variant="outline" onClick={() => setVue("profil")}>
          Profil
        </Button>
      </header>

      {compte.avertissement && (
        <p role="alert" className="mb-4 text-sm text-destructive">
          {compte.avertissement}
        </p>
      )}

      <Tabs value={onglet} onValueChange={setOnglet}>
        <TabsList>
          <TabsTrigger value="chat">Discussion</TabsTrigger>
          {compte.est_admin && <TabsTrigger value="comptes">Comptes</TabsTrigger>}
          {compte.est_admin && <TabsTrigger value="consommations">Consommations</TabsTrigger>}
        </TabsList>
        <TabsContent value="chat">
          <OngletChat />
        </TabsContent>
        {compte.est_admin && (
          <TabsContent value="comptes">
            <OngletComptes />
          </TabsContent>
        )}
        {compte.est_admin && (
          <TabsContent value="consommations">
            <OngletConsommations />
          </TabsContent>
        )}
      </Tabs>
    </main>
  );
}
