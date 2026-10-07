import { useState, type FormEvent } from "react";
import type { UseMutationResult } from "@tanstack/react-query";

import logoBbassAgentsIa from "@/assets/logo-bbass-agents-ia.jpg";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Compte } from "@/hooks/useSession";
import { messageErreur } from "@/lib/api";

interface EcranConnexionProps {
  connexion: UseMutationResult<Compte, Error, { identifiant: string; motDePasse: string }>;
}

export function EcranConnexion({ connexion }: Readonly<EcranConnexionProps>) {
  const [identifiant, setIdentifiant] = useState("");
  const [motDePasse, setMotDePasse] = useState("");

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    connexion.mutate({ identifiant, motDePasse });
  }

  const messageErreurConnexion = messageErreur(connexion.error, "La connexion a échoué. Réessayez plus tard.");

  return (
    <main className="mx-auto mt-24 w-full max-w-sm">
      <img
        src={logoBbassAgentsIa}
        alt="BBASS Agents IA"
        className="mb-8 h-16 w-auto max-w-full object-contain"
      />
      <h1 className="mb-6 text-xl font-semibold">Connexion</h1>
      <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="identifiant">Identifiant</Label>
          <Input
            id="identifiant"
            name="identifiant"
            autoComplete="username"
            required
            value={identifiant}
            onChange={(evenement) => setIdentifiant(evenement.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="mot-de-passe">Mot de passe</Label>
          <Input
            id="mot-de-passe"
            name="mot-de-passe"
            type="password"
            autoComplete="current-password"
            required
            value={motDePasse}
            onChange={(evenement) => setMotDePasse(evenement.target.value)}
          />
        </div>
        <Button type="submit" disabled={connexion.isPending}>
          Se connecter
        </Button>
        {messageErreurConnexion && (
          <p role="alert" className="text-sm text-destructive">
            {messageErreurConnexion}
          </p>
        )}
      </form>
    </main>
  );
}
