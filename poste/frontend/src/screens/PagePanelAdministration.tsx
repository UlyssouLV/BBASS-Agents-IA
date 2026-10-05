import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useComptesConsommationQuery, useComptesQuery } from "@/hooks/useComptes";
import { usePerfChargementPage } from "@/lib/instrumentationTemps";
import { OngletComptes } from "@/onglets/OngletComptes";
import { OngletConsommations } from "@/onglets/OngletConsommations";

interface PagePanelAdministrationProps {
  onRetour: () => void;
}

// Page Panel d'administration plein écran regroupant Comptes et
// Consommations (issue #73) : ces deux onglets ne sont plus accessibles
// depuis l'écran Compte, dont ils faisaient partie à plat avant le ticket
// #70. Mêmes fonctionnalités qu'auparavant (création, modification,
// changement de statut administrateur, révocation, suppression de compte,
// classement des comptes par coût) ; seule la présentation change, avec les
// composants shadcn/ui Table et Badge (voir OngletComptes/OngletConsommations).
export function PagePanelAdministration({ onRetour }: Readonly<PagePanelAdministrationProps>) {
  const [onglet, setOnglet] = useState("comptes");

  // Issue #102 : même logique que PageProfil.tsx — les deux onglets sont
  // montés simultanément (TabsContent forceMount), ces appels ne font que
  // lire le statut des requêtes déjà déclenchées par OngletComptes /
  // OngletConsommations (même cache TanStack Query, pas de requête
  // supplémentaire).
  const comptesQuery = useComptesQuery();
  const comptesConsommationQuery = useComptesConsommationQuery();
  usePerfChargementPage("panel-administration", !comptesQuery.isLoading && !comptesConsommationQuery.isLoading);

  return (
    <main className="mx-auto mt-8 w-full max-w-4xl px-4">
      <header className="mb-4 flex items-center justify-between gap-4">
        <h1 className="text-lg font-semibold">Panel d'administration</h1>
        <Button variant="outline" onClick={onRetour}>
          ← Retour au chat
        </Button>
      </header>

      <Tabs value={onglet} onValueChange={setOnglet}>
        <TabsList>
          <TabsTrigger value="comptes">Comptes</TabsTrigger>
          <TabsTrigger value="consommations">Consommations</TabsTrigger>
        </TabsList>
        <TabsContent value="comptes">
          <OngletComptes />
        </TabsContent>
        <TabsContent value="consommations">
          <OngletConsommations />
        </TabsContent>
      </Tabs>
    </main>
  );
}
