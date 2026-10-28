import { useEffect, useState, type FormEvent } from "react";
import { Ellipsis } from "lucide-react";
import { toast } from "sonner";

import { DialogueAPropos } from "@/components/DialogueAPropos";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useConfiguration,
  useEnregistrerConfiguration,
  useOuvrirDossierConfiguration,
  useTesterConnexion,
  type Configuration,
} from "@/hooks/useConfiguration";
import { messageErreur } from "@/lib/api";
import { cn } from "@/lib/utils";

interface MenuConfigurationProps {
  // Écran de connexion : la Configuration s'ouvre d'elle-même tant que
  // l'adresse du Serveur BBASS est inconnue (adresse prod vide en 1.6.2).
  ouvrirSiAdresseInconnue?: boolean;
  className?: string;
}

// Menu « … » (spec 1.6.2, point 9) : accessible sans connexion, depuis
// l'écran de connexion, et une fois connecté depuis la page Profil.
export function MenuConfiguration({ ouvrirSiAdresseInconnue = false, className }: Readonly<MenuConfigurationProps>) {
  const configuration = useConfiguration();
  const ouvrirDossier = useOuvrirDossierConfiguration();
  const [configurationOuverte, setConfigurationOuverte] = useState(false);
  const [aProposOuvert, setAProposOuvert] = useState(false);
  const [ouvertureAutomatiqueFaite, setOuvertureAutomatiqueFaite] = useState(false);

  const adresseInconnue = configuration.data?.modifiable === true && configuration.data.hote === "";
  useEffect(() => {
    if (ouvrirSiAdresseInconnue && adresseInconnue && !ouvertureAutomatiqueFaite) {
      setOuvertureAutomatiqueFaite(true);
      setConfigurationOuverte(true);
    }
  }, [ouvrirSiAdresseInconnue, adresseInconnue, ouvertureAutomatiqueFaite]);

  function ouvrirLeDossier() {
    ouvrirDossier.mutate(undefined, {
      onError: (erreur) => toast.error(messageErreur(erreur, "Le dossier de configuration n'a pas pu être ouvert.")),
    });
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="ghost" size="icon" className={className} aria-label="Plus d'options">
            <Ellipsis aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setConfigurationOuverte(true)}>Configuration</DropdownMenuItem>
          <DropdownMenuItem onSelect={ouvrirLeDossier}>Ouvrir le dossier de configuration</DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setAProposOuvert(true)}>À propos</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={configurationOuverte} onOpenChange={setConfigurationOuverte}>
        <DialogContent>
          {configuration.data ? (
            <FormulaireConfiguration configuration={configuration.data} onFermer={() => setConfigurationOuverte(false)} />
          ) : (
            <DialogHeader>
              <DialogTitle>Configuration</DialogTitle>
              <DialogDescription role={configuration.error ? "alert" : undefined}>
                {messageErreur(configuration.error, "Impossible de lire la configuration.") ?? "Chargement…"}
              </DialogDescription>
            </DialogHeader>
          )}
        </DialogContent>
      </Dialog>
      <DialogueAPropos ouvert={aProposOuvert} onOuvertChange={setAProposOuvert} />
    </>
  );
}

interface FormulaireConfigurationProps {
  configuration: Configuration;
  onFermer: () => void;
}

function FormulaireConfiguration({ configuration, onFermer }: Readonly<FormulaireConfigurationProps>) {
  const [hote, setHote] = useState(configuration.hote);
  const [port, setPort] = useState(String(configuration.port));
  const tester = useTesterConnexion();
  const enregistrer = useEnregistrerConfiguration();
  const serveur = { hote: hote.trim(), port: Number(port) };

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    enregistrer.mutate(serveur, {
      onSuccess: () => {
        toast.success("Adresse du Serveur BBASS enregistrée.");
        onFermer();
      },
    });
  }

  // Un résultat de test ne vaut que pour l'adresse testée.
  function modifier(action: () => void) {
    action();
    tester.reset();
  }

  const erreur = messageErreur(tester.error ?? enregistrer.error, "La configuration n'a pas pu être enregistrée.");

  return (
    <form onSubmit={gererEnvoi} className="flex flex-col gap-4">
      <DialogHeader>
        <DialogTitle>Configuration</DialogTitle>
        <DialogDescription>
          {configuration.modifiable
            ? "Adresse du Serveur BBASS auquel ce poste est relié."
            : "En développement, l'adresse du Serveur BBASS se règle dans le fichier .env (VM_CENTRALE_BASE_URL)."}
        </DialogDescription>
      </DialogHeader>
      <fieldset disabled={!configuration.modifiable} className="flex flex-col gap-4">
        <legend className="mb-1 text-sm font-semibold">Serveur BBASS</legend>
        <div className="grid grid-cols-[1fr_7rem] gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="configuration-hote">Hôte</Label>
            <Input
              id="configuration-hote"
              placeholder="10.0.0.5"
              required
              value={hote}
              onChange={(evenement) => modifier(() => setHote(evenement.target.value))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="configuration-port">Port</Label>
            <Input
              id="configuration-port"
              type="number"
              min={1}
              max={65535}
              required
              value={port}
              onChange={(evenement) => modifier(() => setPort(evenement.target.value))}
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            variant="outline"
            disabled={tester.isPending || !serveur.hote}
            onClick={() => tester.mutate(serveur)}
          >
            {tester.isPending ? "Test en cours…" : "Tester la connexion"}
          </Button>
          {tester.data && (
            <p
              role="status"
              className={cn("text-sm font-medium", tester.data.joignable ? "text-emerald-700" : "text-amber-700")}
            >
              {tester.data.joignable
                ? `Connecté à BBASS v${tester.data.version}`
                : "Serveur BBASS injoignable à cette adresse."}
            </p>
          )}
        </div>
      </fieldset>
      {erreur && (
        <p role="alert" className="text-sm text-destructive">
          {erreur}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onFermer}>
          Annuler
        </Button>
        <Button type="submit" disabled={!configuration.modifiable || enregistrer.isPending}>
          Enregistrer
        </Button>
      </DialogFooter>
    </form>
  );
}
