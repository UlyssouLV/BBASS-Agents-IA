import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
