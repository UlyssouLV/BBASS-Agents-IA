import { useState } from "react";
import type { UseMutationResult } from "@tanstack/react-query";

import { EnteteProfil } from "@/components/EnteteProfil";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useConsommationQuery } from "@/hooks/useConsommation";
import { useProfilTravailQuery } from "@/hooks/useProfilTravail";
import { usePerfChargementPage } from "@/lib/instrumentationTemps";
import { OngletConsommation } from "@/onglets/OngletConsommation";
import { OngletProfilTravail } from "@/onglets/OngletProfilTravail";

interface PageProfilProps {
  deconnexion: UseMutationResult<void, Error, void>;
  onRetour: () => void;
}

// Page Profil plein écran regroupant Consommation et Profil de travail (issue
// #72) : ces deux onglets ne sont plus accessibles depuis l'écran Compte,
// dont ils faisaient partie à plat avant le ticket #70.
export function PageProfil({ deconnexion, onRetour }: Readonly<PageProfilProps>) {
  const [onglet, setOnglet] = useState("consommation");

  // Issue #102 : les deux onglets sont montés simultanément (TabsContent
  // forceMount, voir components/ui/tabs.tsx), donc leurs requêtes démarrent
  // toutes les deux dès l'arrivée sur cette page — appelées ici uniquement
  // pour leur statut (même cache TanStack Query que les onglets eux-mêmes,
  // pas de requête supplémentaire).
  const consommationQuery = useConsommationQuery();
  const profilTravailQuery = useProfilTravailQuery();
  usePerfChargementPage("profil", !consommationQuery.isLoading && !profilTravailQuery.isLoading);

  return (
    <main className="mx-auto mt-8 w-full max-w-4xl px-4">
      <EnteteProfil
        onRetour={onRetour}
        onDeconnexion={() => deconnexion.mutate()}
        deconnexionEnCours={deconnexion.isPending}
      />

      <Tabs value={onglet} onValueChange={setOnglet}>
        <TabsList>
          <TabsTrigger value="consommation">Consommation</TabsTrigger>
          <TabsTrigger value="profil-travail">Profil de travail</TabsTrigger>
        </TabsList>
        <TabsContent value="consommation">
          <p className="mb-4 text-sm text-muted-foreground">
            Le coût de vos échanges avec l'IA, par conversation et par catégorie (chat, pièce jointe).
          </p>
          <OngletConsommation />
        </TabsContent>
        <TabsContent value="profil-travail">
          <p className="mb-4 text-sm text-muted-foreground">
            Les informations que l'IA retient sur votre façon de travailler, pour personnaliser ses réponses.
          </p>
          <OngletProfilTravail />
        </TabsContent>
      </Tabs>
    </main>
  );
}
