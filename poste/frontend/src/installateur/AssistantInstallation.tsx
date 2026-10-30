import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Check, FolderOpen, Monitor, Power } from "lucide-react";

import logoBbass from "@/assets/logo-bbass.png";
import logoBbassAgentsIa from "@/assets/logo-bbass-agents-ia.jpg";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  installer,
  lancerBbass,
  lireInformations,
  testerServeur,
  type EtatServeur,
  type Informations,
  type Progression,
} from "@/installateur/setup";
import { cn } from "@/lib/utils";

// Assistant du Setup (spec 1.6.2, point 8), au style de l'écran de connexion
// 1.6.2 : marque et étapes à gauche, étape courante à droite.
const ETAPES = ["Bienvenue", "Serveur BBASS", "Options", "Installation"] as const;
type Etape = 0 | 1 | 2 | 3;

// Le test en direct attend que l'adresse ne bouge plus.
const DELAI_AVANT_TEST_MS = 500;

export function AssistantInstallation() {
  const [informations, setInformations] = useState<Informations | null>(null);
  const [etape, setEtape] = useState<Etape>(0);
  const [hote, setHote] = useState("");
  const [port, setPort] = useState("8000");
  const [demarrageWindows, setDemarrageWindows] = useState(true);
  const [raccourciBureau, setRaccourciBureau] = useState(true);

  useEffect(() => {
    lireInformations()
      .then((lues) => {
        setInformations(lues);
        setHote(lues.hote);
        setPort(String(lues.port));
      })
      .catch((erreur: unknown) => console.error("Informations du Setup non lues :", erreur));
  }, []);

  return (
    <main className="grid h-svh grid-cols-[15rem_minmax(0,1fr)] select-none">
      <aside className="relative flex flex-col overflow-hidden bg-primary p-8 text-primary-foreground">
        <img src={logoBbass} alt="" className="h-9 w-auto self-start rounded-md bg-primary-foreground p-1.5" />
        <ol className="relative z-10 mt-12 flex flex-col gap-4 text-sm" aria-label="Étapes de l'installation">
          {ETAPES.map((nom, index) => (
            <li
              key={nom}
              aria-current={index === etape ? "step" : undefined}
              className={cn(
                "flex items-center gap-3 transition-colors",
                index === etape ? "font-semibold text-primary-foreground" : "text-primary-foreground/55"
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "flex size-6 items-center justify-center rounded-full border text-xs",
                  index < etape && "border-accent bg-accent text-accent-foreground",
                  index === etape && "border-primary-foreground",
                  index > etape && "border-primary-foreground/30"
                )}
              >
                {index < etape ? <Check className="size-3.5" /> : index + 1}
              </span>
              {nom}
            </li>
          ))}
        </ol>
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-20 -bottom-20 size-56 rounded-full border-[2.5rem] border-accent/20"
        />
      </aside>

      <section className="flex min-h-0 flex-col px-10 py-9">
        {informations === null ? (
          <p className="m-auto text-sm text-muted-foreground">Chargement…</p>
        ) : (
          <>
            {etape === 0 && <EtapeBienvenue informations={informations} onContinuer={() => setEtape(1)} />}
            {etape === 1 && (
              <EtapeServeur
                hote={hote}
                port={port}
                onHote={setHote}
                onPort={setPort}
                onRetour={() => setEtape(0)}
                onContinuer={() => setEtape(2)}
              />
            )}
            {etape === 2 && (
              <EtapeOptions
                demarrageWindows={demarrageWindows}
                raccourciBureau={raccourciBureau}
                onDemarrageWindows={setDemarrageWindows}
                onRaccourciBureau={setRaccourciBureau}
                onRetour={() => setEtape(1)}
                onInstaller={() => setEtape(3)}
              />
            )}
            {etape === 3 && (
              <EtapeInstallation
                options={{ hote: hote.trim(), port: Number(port), demarrageWindows, raccourciBureau }}
                onRetour={() => setEtape(2)}
              />
            )}
          </>
        )}
      </section>
    </main>
  );
}

function Titre({ titre, description }: Readonly<{ titre: string; description: string }>) {
  return (
    <header className="mb-7">
      <p className="mb-3 h-1 w-10 rounded-full bg-accent" aria-hidden="true" />
      <h1 className="text-2xl font-semibold">{titre}</h1>
      <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
    </header>
  );
}

function Pied({ children }: Readonly<{ children: ReactNode }>) {
  return <footer className="mt-auto flex justify-end gap-3 pt-6">{children}</footer>;
}

function EtapeBienvenue({ informations, onContinuer }: Readonly<{ informations: Informations; onContinuer: () => void }>) {
  return (
    <>
      <img src={logoBbassAgentsIa} alt="BBASS Agents IA" className="mb-8 h-14 w-auto self-start object-contain" />
      <Titre
        titre="Bienvenue"
        description="Cet assistant installe BBASS sur ce poste, pour votre compte Windows, sans droits administrateur."
      />
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-6 gap-y-3 rounded-lg border bg-muted/50 p-4 text-sm">
        <dt className="text-muted-foreground">Version</dt>
        <dd className="font-medium">v{informations.version}</dd>
        <dt className="text-muted-foreground">Emplacement</dt>
        <dd className="flex items-center gap-2 font-medium break-all">
          <FolderOpen className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          {informations.emplacement}
        </dd>
      </dl>
      <Pied>
        <Button type="button" onClick={onContinuer} autoFocus>
          Continuer
        </Button>
      </Pied>
    </>
  );
}

interface EtapeServeurProps {
  hote: string;
  port: string;
  onHote: (hote: string) => void;
  onPort: (port: string) => void;
  onRetour: () => void;
  onContinuer: () => void;
}

function EtapeServeur({ hote, port, onHote, onPort, onRetour, onContinuer }: Readonly<EtapeServeurProps>) {
  const [etat, setEtat] = useState<EtatServeur | "test" | null>(null);
  const portValide = /^\d+$/.test(port) && Number(port) >= 1 && Number(port) <= 65535;
  const adresseComplete = hote.trim() !== "" && portValide;

  // Test en direct sur /sante : un résultat ne vaut que pour l'adresse testée.
  useEffect(() => {
    if (!adresseComplete) {
      setEtat(null);
      return;
    }
    let abandonne = false;
    setEtat("test");
    const minuterie = setTimeout(() => {
      testerServeur(hote.trim(), Number(port))
        .then((resultat) => {
          if (!abandonne) setEtat(resultat);
        })
        .catch(() => {
          if (!abandonne) setEtat({ joignable: false, version: null });
        });
    }, DELAI_AVANT_TEST_MS);
    return () => {
      abandonne = true;
      clearTimeout(minuterie);
    };
  }, [hote, port, adresseComplete]);

  function gererEnvoi(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    if (adresseComplete) onContinuer();
  }

  return (
    <form onSubmit={gererEnvoi} className="flex min-h-0 flex-1 flex-col">
      <Titre
        titre="Serveur BBASS"
        description="Adresse du Serveur BBASS du cabinet. BBASS se mettra à sa version à chaque lancement."
      />
      <div className="grid grid-cols-[minmax(0,1fr)_7rem] gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="setup-hote">Hôte</Label>
          <Input
            id="setup-hote"
            placeholder="serveur-bbass"
            required
            autoFocus
            value={hote}
            onChange={(evenement) => onHote(evenement.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="setup-port">Port</Label>
          <Input
            id="setup-port"
            type="number"
            min={1}
            max={65535}
            required
            value={port}
            onChange={(evenement) => onPort(evenement.target.value)}
          />
        </div>
      </div>
      <PastilleTest etat={etat} />
      <Pied>
        <Button type="button" variant="outline" onClick={onRetour}>
          Retour
        </Button>
        <Button type="submit" disabled={!adresseComplete}>
          Continuer
        </Button>
      </Pied>
    </form>
  );
}

// Vert avec la version, orange sinon (continuer reste permis).
function PastilleTest({ etat }: Readonly<{ etat: EtatServeur | "test" | null }>) {
  if (etat === null) {
    return null;
  }
  const joignable = etat !== "test" && etat.joignable;
  return (
    <div className="mt-6 flex flex-col gap-2">
      <p
        role="status"
        className={cn(
          "inline-flex items-center gap-2 self-start rounded-full border px-3 py-1 text-xs font-medium",
          etat === "test" && "border-border bg-muted text-muted-foreground",
          etat !== "test" && joignable && "border-emerald-600/25 bg-emerald-50 text-emerald-800",
          etat !== "test" && !joignable && "border-amber-600/30 bg-amber-50 text-amber-900"
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "size-2 rounded-full",
            etat === "test" && "animate-pulse bg-muted-foreground",
            etat !== "test" && (joignable ? "bg-emerald-600" : "bg-amber-500")
          )}
        />
        {etat === "test"
          ? "Test de la connexion…"
          : joignable
            ? `Connecté à BBASS v${etat.version}`
            : "Serveur BBASS injoignable à cette adresse."}
      </p>
      {etat !== "test" && !joignable && (
        <p className="text-xs text-muted-foreground">
          Vous pouvez continuer : l'adresse se change ensuite dans le menu « … » de l'écran de connexion.
        </p>
      )}
    </div>
  );
}

interface EtapeOptionsProps {
  demarrageWindows: boolean;
  raccourciBureau: boolean;
  onDemarrageWindows: (valeur: boolean) => void;
  onRaccourciBureau: (valeur: boolean) => void;
  onRetour: () => void;
  onInstaller: () => void;
}

function EtapeOptions(props: Readonly<EtapeOptionsProps>) {
  return (
    <>
      <Titre titre="Options" description="Vous pourrez revenir sur ces choix en réinstallant BBASS." />
      <div className="flex flex-col gap-3">
        <Option
          id="setup-demarrage"
          icone={<Power className="size-4" aria-hidden="true" />}
          titre="Démarrer avec Windows"
          description="BBASS démarre en fond à l'ouverture de session et se met à jour à ce moment."
          coche={props.demarrageWindows}
          onCoche={props.onDemarrageWindows}
        />
        <Option
          id="setup-bureau"
          icone={<Monitor className="size-4" aria-hidden="true" />}
          titre="Raccourci sur le Bureau"
          description="En plus du raccourci du menu Démarrer."
          coche={props.raccourciBureau}
          onCoche={props.onRaccourciBureau}
        />
      </div>
      <Pied>
        <Button type="button" variant="outline" onClick={props.onRetour}>
          Retour
        </Button>
        <Button type="button" onClick={props.onInstaller} autoFocus>
          Installer
        </Button>
      </Pied>
    </>
  );
}

interface OptionProps {
  id: string;
  icone: ReactNode;
  titre: string;
  description: string;
  coche: boolean;
  onCoche: (valeur: boolean) => void;
}

function Option({ id, icone, titre, description, coche, onCoche }: Readonly<OptionProps>) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-start gap-3 rounded-lg border p-4 transition-colors hover:bg-muted/50 has-[[data-state=checked]]:border-primary/40"
    >
      <Checkbox id={id} checked={coche} onCheckedChange={(valeur) => onCoche(valeur === true)} className="mt-0.5" />
      <span className="flex flex-col gap-0.5">
        <span className="flex items-center gap-2 text-sm font-medium">
          {icone}
          {titre}
        </span>
        <span className="text-xs text-muted-foreground">{description}</span>
      </span>
    </label>
  );
}

interface EtapeInstallationProps {
  options: Parameters<typeof installer>[0];
  onRetour: () => void;
}

function EtapeInstallation({ options, onRetour }: Readonly<EtapeInstallationProps>) {
  const [progression, setProgression] = useState<Progression>({ etape: "Préparation…", fraction: 0 });
  const [statut, setStatut] = useState<"en-cours" | "faite" | "lancement">("en-cours");
  const [erreur, setErreur] = useState<string | null>(null);
  const [essai, setEssai] = useState(0);
  const essaiLance = useRef(-1);
  const { hote, port, demarrageWindows, raccourciBureau } = options;

  useEffect(() => {
    // Une seule installation par essai (StrictMode rejoue les effets en dev).
    if (essaiLance.current === essai) return;
    essaiLance.current = essai;
    setErreur(null);
    setStatut("en-cours");
    installer({ hote, port, demarrageWindows, raccourciBureau }, setProgression).then(
      () => setStatut("faite"),
      (cause: unknown) => setErreur(String(cause))
    );
  }, [hote, port, demarrageWindows, raccourciBureau, essai]);

  function lancer() {
    setStatut("lancement");
    lancerBbass().catch((cause: unknown) => {
      setStatut("faite");
      setErreur(String(cause));
    });
  }

  const faite = statut !== "en-cours";
  return (
    <>
      <Titre
        titre={faite ? "BBASS est installé" : "Installation"}
        description={
          faite
            ? "Au lancement, BBASS se met à la version du Serveur BBASS puis ouvre l'écran de connexion."
            : "Quelques secondes : BBASS est copié sur ce poste."
        }
      />
      <div className="flex flex-col gap-2">
        <div
          role="progressbar"
          aria-label="Installation"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progression.fraction * 100)}
          className="h-1.5 overflow-hidden rounded-full bg-muted"
        >
          <div
            className={cn("h-full rounded-full transition-[width] duration-300", erreur ? "bg-destructive" : "bg-accent")}
            style={{ width: `${Math.round(progression.fraction * 100)}%` }}
          />
        </div>
        <p className="text-sm text-muted-foreground">{progression.etape}</p>
      </div>
      {erreur && (
        <p role="alert" className="mt-4 text-sm text-destructive">
          {erreur}
        </p>
      )}
      <Pied>
        {erreur && !faite && (
          <>
            <Button type="button" variant="outline" onClick={onRetour}>
              Retour
            </Button>
            <Button type="button" onClick={() => setEssai((n) => n + 1)}>
              Réessayer
            </Button>
          </>
        )}
        {faite && (
          <Button type="button" onClick={lancer} disabled={statut === "lancement"} autoFocus>
            Lancer BBASS
          </Button>
        )}
      </Pied>
    </>
  );
}
