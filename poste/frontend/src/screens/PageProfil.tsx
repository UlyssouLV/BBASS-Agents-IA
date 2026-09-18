import { useState } from "react";
import type { UseMutationResult } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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

  return (
    <main className="mx-auto mt-8 w-full max-w-4xl px-4">
      <header className="mb-4 flex items-center justify-between gap-4">
        <Button variant="outline" onClick={onRetour}>
          ← Retour au chat
        </Button>
        <h1 className="text-lg font-semibold">Profil</h1>
        <Button variant="outline" onClick={() => deconnexion.mutate()} disabled={deconnexion.isPending}>
          Se déconnecter
        </Button>
      </header>

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
