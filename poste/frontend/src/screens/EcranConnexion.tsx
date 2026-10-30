import { useState, type FormEvent } from "react";
import type { UseMutationResult } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";

import logoBbass from "@/assets/logo-bbass.png";
import logoBbassAgentsIa from "@/assets/logo-bbass-agents-ia.jpg";
import { MenuConfiguration } from "@/components/MenuConfiguration";
import { PastilleServeurBbass } from "@/components/PastilleServeurBbass";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Compte } from "@/hooks/useSession";
import { messageErreur } from "@/lib/api";

interface EcranConnexionProps {
  connexion: UseMutationResult<Compte, Error, { identifiant: string; motDePasse: string }>;
}

// Spec 1.6.2, point 9 : deux panneaux (marque à gauche, formulaire à droite)
// dans le style 1.2.1, pastille d'état du Serveur BBASS et menu « … »
// (Configuration, dossier de configuration) accessibles sans connexion.
export function EcranConnexion({ connexion }: Readonly<EcranConnexionProps>) {
  const [identifiant, setIdentifiant] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [motDePasseVisible, setMotDePasseVisible] = useState(false);

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    connexion.mutate({ identifiant, motDePasse });
  }

  const messageErreurConnexion = messageErreur(connexion.error, "La connexion a échoué. Réessayez plus tard.");

  return (
    <main className="grid min-h-full md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <section
        aria-label="BBASS"
        className="relative hidden flex-col justify-between overflow-hidden bg-primary p-10 text-primary-foreground md:flex"
      >
        <img src={logoBbass} alt="" className="h-10 w-auto self-start rounded-md bg-primary-foreground p-1.5" />
        <div className="relative z-10 max-w-sm">
          <p className="mb-3 h-1 w-12 rounded-full bg-accent" aria-hidden="true" />
          <h2 className="text-3xl leading-tight font-semibold">L'assistant IA du cabinet BBASS.</h2>
          <p className="mt-3 text-sm text-primary-foreground/70">
            Vos conversations, vos documents et vos dossiers, au même endroit.
          </p>
        </div>
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-24 -bottom-24 size-80 rounded-full border-[3rem] border-accent/20"
        />
      </section>

      <section className="relative flex flex-col items-center justify-center px-6 py-16">
        <MenuConfiguration ouvrirSiAdresseInconnue className="absolute top-4 right-4" />
        <div className="w-full max-w-sm">
          <img
            src={logoBbassAgentsIa}
            alt="BBASS Agents IA"
            className="mb-8 h-14 w-auto max-w-full object-contain"
          />
          <h1 className="mb-1 text-2xl font-semibold">Connexion</h1>
          <p className="mb-6 text-sm text-muted-foreground">Connectez-vous avec votre identifiant BBASS.</p>
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
              <div className="relative">
                <Input
                  id="mot-de-passe"
                  name="mot-de-passe"
                  type={motDePasseVisible ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  className="pr-10"
                  value={motDePasse}
                  onChange={(evenement) => setMotDePasse(evenement.target.value)}
                />
                <button
                  type="button"
                  onClick={() => setMotDePasseVisible((visible) => !visible)}
                  aria-label={motDePasseVisible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                  aria-pressed={motDePasseVisible}
                  className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
                >
                  {motDePasseVisible ? (
                    <EyeOff className="size-4" aria-hidden="true" />
                  ) : (
                    <Eye className="size-4" aria-hidden="true" />
                  )}
                </button>
              </div>
            </div>
            <Button type="submit" disabled={connexion.isPending} className="mt-2">
              Connexion
            </Button>
            {messageErreurConnexion && (
              <p role="alert" className="text-sm text-destructive">
                {messageErreurConnexion}
              </p>
            )}
          </form>
          <PastilleServeurBbass className="mt-8" />
        </div>
      </section>
    </main>
  );
}
