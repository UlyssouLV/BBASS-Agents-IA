import { useState, type FormEvent } from "react";
import type { UseMutationResult } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Compte } from "@/hooks/useSession";
import { ErreurApi } from "@/lib/api";

interface EcranChangementMotDePasseProps {
  changerMotDePasse: UseMutationResult<Compte, Error, string>;
}

export function EcranChangementMotDePasse({ changerMotDePasse }: EcranChangementMotDePasseProps) {
  const [nouveauMotDePasse, setNouveauMotDePasse] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [erreurLocale, setErreurLocale] = useState<string | null>(null);

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    setErreurLocale(null);

    if (nouveauMotDePasse !== confirmation) {
      setErreurLocale("Les mots de passe saisis ne correspondent pas.");
      return;
    }

    changerMotDePasse.mutate(nouveauMotDePasse, {
      onSuccess: () => {
        setNouveauMotDePasse("");
        setConfirmation("");
      },
    });
  }

  const erreurMutation = changerMotDePasse.error;
  const messageErreur =
    erreurLocale ??
    (erreurMutation
      ? erreurMutation instanceof ErreurApi
        ? erreurMutation.message
        : "Le changement de mot de passe a échoué. Réessayez plus tard."
      : null);

  return (
    <main className="mx-auto mt-24 w-full max-w-sm">
      <h1 className="mb-2 text-xl font-semibold">Changement de mot de passe requis</h1>
      <p className="mb-6 text-sm text-muted-foreground">
        Vous devez choisir un nouveau mot de passe avant d'accéder à l'application.
      </p>
      <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="nouveau-mot-de-passe">Nouveau mot de passe</Label>
          <Input
            id="nouveau-mot-de-passe"
            name="nouveau-mot-de-passe"
            type="password"
            autoComplete="new-password"
            required
            value={nouveauMotDePasse}
            onChange={(evenement) => setNouveauMotDePasse(evenement.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="confirmation-mot-de-passe">Confirmer le nouveau mot de passe</Label>
          <Input
            id="confirmation-mot-de-passe"
            name="confirmation-mot-de-passe"
            type="password"
            autoComplete="new-password"
            required
            value={confirmation}
            onChange={(evenement) => setConfirmation(evenement.target.value)}
          />
        </div>
        <Button type="submit" disabled={changerMotDePasse.isPending}>
          Changer le mot de passe
        </Button>
        {messageErreur && (
          <p role="alert" className="text-sm text-destructive">
            {messageErreur}
          </p>
        )}
      </form>
    </main>
  );
}
