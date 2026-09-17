import { useState } from "react";
import type { UseMutationResult } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Compte } from "@/hooks/useSession";
import { OngletChat } from "@/onglets/OngletChat";

interface EcranCompteProps {
  compte: Compte;
  deconnexion: UseMutationResult<void, Error, void>;
}

// Onglets encore vides pour cette version, hors Discussion : remplis par les
// tickets suivants (OngletConsommation, OngletProfilTravail, OngletComptes,
// OngletConsommations — voir docs/specs/v1.2.0-interface-poste.md,
// Implementation Decisions).
export function EcranCompte({ compte, deconnexion }: EcranCompteProps) {
  const [onglet, setOnglet] = useState("chat");

  const poleAgence = [compte.poles.join(", "), compte.agence].filter(Boolean).join(" — ");

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
        <Button variant="outline" onClick={() => deconnexion.mutate()} disabled={deconnexion.isPending}>
          Se déconnecter
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
          <TabsTrigger value="consommation">Consommation</TabsTrigger>
          <TabsTrigger value="profil-travail">Profil de travail</TabsTrigger>
          {compte.est_admin && <TabsTrigger value="comptes">Comptes</TabsTrigger>}
          {compte.est_admin && <TabsTrigger value="consommations">Consommations</TabsTrigger>}
        </TabsList>
        <TabsContent value="chat">
          <OngletChat />
        </TabsContent>
        <TabsContent value="consommation" />
        <TabsContent value="profil-travail" />
        {compte.est_admin && <TabsContent value="comptes" />}
        {compte.est_admin && <TabsContent value="consommations" />}
      </Tabs>
    </main>
  );
}
