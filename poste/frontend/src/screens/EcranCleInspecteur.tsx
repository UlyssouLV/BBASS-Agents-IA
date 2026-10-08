import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface EcranCleInspecteurProps {
  erreur: string | null;
  onValider: (cle: string) => void;
  /** Le poste prend le focus à l'ouverture. La doc le laisse au lecteur. */
  focusAutomatique?: boolean;
}

// Même champ, même libellé et même comportement que la saisie de la Clé
// d'administration VM d'OngletComptes : rien n'est chargé avant qu'elle soit saisie.
export function EcranCleInspecteur({
  erreur,
  onValider,
  focusAutomatique = true,
}: Readonly<EcranCleInspecteurProps>) {
  const [saisie, setSaisie] = useState("");

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    onValider(saisie);
  }

  return (
    <main className="mx-auto mt-24 w-full max-w-sm">
      <h1 className="mb-2 text-xl font-semibold">Inspecteur des échanges avec le modèle</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        La Clé d'administration VM est requise pour ouvrir le mode développeur.
      </p>
      <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="inspecteur-cle">Clé d'administration VM</Label>
          <Input
            id="inspecteur-cle"
            type="password"
            required
            autoFocus={focusAutomatique}
            value={saisie}
            onChange={(evenement) => setSaisie(evenement.target.value)}
          />
        </div>
        <Button type="submit">Ouvrir l'inspecteur</Button>
        {erreur && (
          <p role="alert" className="text-sm text-destructive">
            {erreur}
          </p>
        )}
      </form>
    </main>
  );
}
