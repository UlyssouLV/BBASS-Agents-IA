import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import {
  File,
  FileImage,
  FileSpreadsheet,
  FileText,
  FileType,
  Loader2,
  Paperclip,
  X,
  type LucideIcon,
} from "lucide-react";
import Markdown, { type Components } from "react-markdown";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useConversationQuery,
  useCreerConversationMutation,
  useEnvoyerMessageMutation,
  type Message,
} from "@/hooks/useConversations";
import { messageErreur } from "@/lib/api";
import { cn } from "@/lib/utils";

// Mêmes extensions/types qu'app.js (formulaireNouvelleConversation /
// formulaireChat) : la VM centrale n'accepte pas d'autres pièces jointes
// (spec 1.1.2).
const TYPES_PIECE_JOINTE_ACCEPTES = ".pdf,.docx,.xlsx,image/jpeg,image/png,image/webp,image/gif";

// Issue #77 : icône affichée sous le champ de saisie une fois un fichier
// sélectionné, selon son type (déduit du nom de fichier pour PDF/Word/Excel,
// du type MIME pour les images — même distinction que
// TYPES_PIECE_JOINTE_ACCEPTES ci-dessus).
function typePieceJointe(fichier: File): "pdf" | "word" | "excel" | "image" | "autre" {
  if (fichier.type.startsWith("image/")) {
    return "image";
  }
  const nom = fichier.name.toLowerCase();
  if (nom.endsWith(".pdf")) {
    return "pdf";
  }
  if (nom.endsWith(".docx")) {
    return "word";
  }
  if (nom.endsWith(".xlsx")) {
    return "excel";
  }
  return "autre";
}

const ICONES_PIECE_JOINTE: Record<ReturnType<typeof typePieceJointe>, LucideIcon> = {
  pdf: FileText,
  word: FileType,
  excel: FileSpreadsheet,
  image: FileImage,
  autre: File,
};

function IconePieceJointe({ fichier, className }: Readonly<{ fichier: File; className?: string }>) {
  const Icone = ICONES_PIECE_JOINTE[typePieceJointe(fichier)];
  return <Icone className={className} aria-hidden="true" />;
}

interface OngletChatProps {
  conversationOuverteId: number | null;
  onConversationCreee: (id: number) => void;
}

// Issue #77 : la pièce jointe (optionnelle) n'est plus déposée via un champ
// <input type="file"> visible en permanence sous le champ de message, mais
// via une icône trombone intégrée au champ de saisie (clic) et le
// glisser-déposer sur ce même champ. Le fichier retenu est ensuite affiché
// sous le champ avec une icône selon son type et un moyen de le retirer.
function ChampMessageAvecPieceJointe({
  id,
  label,
  valeur,
  onChange,
  fichier,
  onFichierChange,
  disabled,
}: Readonly<{
  id: string;
  label: string;
  valeur: string;
  onChange: (valeur: string) => void;
  fichier: File | null;
  onFichierChange: (fichier: File | null) => void;
  disabled: boolean;
}>) {
  const refFichier = useRef<HTMLInputElement>(null);
  const [zoneDepotActive, setZoneDepotActive] = useState(false);

  function gererDepot(evenement: DragEvent<HTMLDivElement>) {
    evenement.preventDefault();
    setZoneDepotActive(false);
    const depose = evenement.dataTransfer.files?.[0];
    if (depose) {
      onFichierChange(depose);
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id} className="sr-only">
        {label}
      </Label>
      <div
        className={cn(
          "relative rounded-2xl transition-colors",
          zoneDepotActive && "outline-2 outline-offset-2 outline-primary bg-primary/5"
        )}
        onDragOver={(evenement) => {
          if (disabled) {
            return;
          }
          evenement.preventDefault();
          setZoneDepotActive(true);
        }}
        onDragLeave={() => setZoneDepotActive(false)}
        onDrop={disabled ? undefined : gererDepot}
      >
        <Textarea
          id={id}
          autoComplete="off"
          required
          rows={3}
          value={valeur}
          onChange={(evenement) => onChange(evenement.target.value)}
          onKeyDown={(evenement) => {
            // Issue #78 : Entrée seule soumet le formulaire (comme le
            // bouton « Envoyer » retiré ci-dessous), Maj+Entrée insère un
            // retour à la ligne (comportement par défaut du textarea, donc
            // pas de preventDefault dans ce cas).
            if (evenement.key === "Enter" && !evenement.shiftKey) {
              evenement.preventDefault();
              evenement.currentTarget.form?.requestSubmit();
            }
          }}
          disabled={disabled}
          className="pr-12"
        />
        <input
          type="file"
          id={`${id}-piece-jointe`}
          accept={TYPES_PIECE_JOINTE_ACCEPTES}
          ref={refFichier}
          disabled={disabled}
          className="sr-only"
          aria-label="Joindre un fichier"
          onChange={(evenement) => {
            onFichierChange(evenement.target.files?.[0] ?? null);
            evenement.target.value = "";
          }}
        />
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute right-2 bottom-2"
          disabled={disabled}
          onClick={() => refFichier.current?.click()}
          aria-label="Joindre un fichier"
        >
          <Paperclip className="size-4" />
        </Button>
      </div>
      {fichier && (
        <div className="flex w-fit items-center gap-2 rounded-lg border bg-muted px-3 py-1.5 text-sm">
          <IconePieceJointe fichier={fichier} className="size-4 shrink-0 text-muted-foreground" />
          <span className="max-w-48 truncate">{fichier.name}</span>
          <button
            type="button"
            onClick={() => onFichierChange(null)}
            disabled={disabled}
            aria-label="Retirer la pièce jointe"
            className="text-muted-foreground hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}

// Issue #93 : allowlist des composants Markdown autorisés dans la bulle de
// message assistant (spec #91, Solution volet 2). Les balises hors de cette
// liste (titres, tableaux, séparateurs, blocs de code, HTML brut, liens,
// images, citations) sont neutralisées par ELEMENTS_MARKDOWN_NEUTRALISES
// ci-dessous : jamais de marqueur Markdown brut affiché à l'écran. Ce
// mapping reste le point d'extension naturel pour de futurs types de blocs
// (cf. feuille de route, section « Plus tard »).
const ESPACEMENT_BLOC_MARKDOWN = "[&:not(:first-child)]:mt-2";
const COMPOSANTS_MARKDOWN_MESSAGE: Components = {
  p: ({ children }) => <p className={ESPACEMENT_BLOC_MARKDOWN}>{children}</p>,
  ul: ({ children }) => <ul className={cn(ESPACEMENT_BLOC_MARKDOWN, "list-disc pl-5")}>{children}</ul>,
  ol: ({ children }) => <ol className={cn(ESPACEMENT_BLOC_MARKDOWN, "list-decimal pl-5")}>{children}</ol>,
};
const ELEMENTS_MARKDOWN_NEUTRALISES = [
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "hr",
  "pre",
  "code",
  "a",
  "img",
  "blockquote",
];

function ContenuMessageAssistant({ texte }: Readonly<{ texte: string }>) {
  return (
    <Markdown components={COMPOSANTS_MARKDOWN_MESSAGE} disallowedElements={ELEMENTS_MARKDOWN_NEUTRALISES} unwrapDisallowed>
      {texte}
    </Markdown>
  );
}

// Issue #84 : le message du collaborateur ne doit pas apparaître d'un bloc
// en haut à droite de la conversation ; il glisse depuis la zone de saisie (juste en
// dessous) vers sa place définitive. requestAnimationFrame plutôt qu'un
// montage direct en position finale : le navigateur doit peindre l'état
// initial (translaté, transparent) avant que la transition CSS vers l'état
// final ne parte, sinon les deux états se confondent en un seul rendu.
function BulleMessageEnvoye({ texte }: Readonly<{ texte: string }>) {
  const [arrivee, setArrivee] = useState(false);

  useEffect(() => {
    const id = window.requestAnimationFrame(() => setArrivee(true));
    return () => window.cancelAnimationFrame(id);
  }, []);

  return (
    <p
      className={cn(
        "self-end rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground transition-all duration-300 ease-out",
        arrivee ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
      )}
    >
      {texte}
    </p>
  );
}

const _INTERVALLE_ANIMATION_FRAPPE_MS = 20;
// Nombre d'étapes cible pour parcourir tout le texte : un pas fixe (comme
// TitreAnimeConversation dans BarreLaterale.tsx) prendrait plusieurs
// secondes sur une réponse longue (contrainte 1.2.1 : « rythme soutenu, pas
// trop lent »). Le nombre de caractères révélés par étape est donc calculé
// pour que l'animation dure toujours environ le même temps, quelle que
// soit la longueur du texte déjà reçu (pas de streaming HTTP, voir issue).
const _NB_ETAPES_ANIMATION_FRAPPE = 60;

// Écrit `texte` progressivement, comme si l'Agent tapait sa réponse.
function TexteAnimeReponse({ texte, onTermine }: Readonly<{ texte: string; onTermine: () => void }>) {
  const [longueurAffichee, setLongueurAffichee] = useState(0);
  const animationTermineeRef = useRef(false);
  const caracteresParEtape = Math.max(1, Math.ceil(texte.length / _NB_ETAPES_ANIMATION_FRAPPE));

  useEffect(() => {
    if (longueurAffichee >= texte.length) {
      if (!animationTermineeRef.current) {
        animationTermineeRef.current = true;
        onTermine();
      }
      return;
    }
    const delai = window.setTimeout(
      () => setLongueurAffichee((longueur) => Math.min(texte.length, longueur + caracteresParEtape)),
      _INTERVALLE_ANIMATION_FRAPPE_MS
    );
    return () => window.clearTimeout(delai);
  }, [longueurAffichee, texte, caracteresParEtape, onTermine]);

  return <ContenuMessageAssistant texte={texte.slice(0, longueurAffichee)} />;
}

// Réécriture React de la section #onglet-chat d'app.js : ne porte plus que
// la conversation ouverte (nouvelle conversation ou conversation existante) — la
// liste des conversations et sa création sont montées dans la sidebar
// permanente de l'écran Compte depuis le ticket #74 (voir
// BarreLaterale.tsx et docs/specs/v1.2.1-identite-visuelle-disposition.md),
// `conversationOuverteId` devenant un état partagé porté par EcranCompte.
// Issue #76 : écran de composition centré (accroche + textarea partagé) ;
// les mutations TanStack Query restent inchangées.
//
// Issue #84 : le premier envoi et les envois suivants ne doivent plus
// attendre la réponse d'un bloc. `envoiEnCours` porte l'état visuel de la
// conversation pendant qu'une réponse est en vol, indépendamment de l'accroche ou de la
// conversation ouverte :
// - "attente" : la VM n'a pas encore répondu (indicateur « Réflexion… »).
// - "frappe"  : la réponse est connue et s'écrit progressivement (voir
//   TexteAnimeReponse ci-dessus).
// - "termine" : la frappe est finie ; on attend que `conversationQuery`
//   (invalidée par la mutation) rattrape le nouveau tour avant de rebasculer
//   sur ses données, pour ne jamais faire disparaître puis réapparaître le
//   message pendant que la requête de fond est encore en vol.
// `messagesAvantEnvoiRef` fige la liste affichée avant cet envoi (vide pour
// une toute nouvelle conversation) : tant qu'`envoiEnCours` n'est pas nul,
// la conversation se construit à partir de ce figé + des bulles optimistes plutôt
// que des données live, qui peuvent se mettre à jour avant la fin de
// l'animation.
type PhaseEnvoi = "attente" | "frappe" | "termine";

interface EnvoiEnCours {
  message: string;
  phase: PhaseEnvoi;
  reponse: string;
}

export function OngletChat({ conversationOuverteId, onConversationCreee }: Readonly<OngletChatProps>) {
  const [champNouveauMessage, setChampNouveauMessage] = useState("");
  const [champMessage, setChampMessage] = useState("");
  const [fichierNouvelleConversation, setFichierNouvelleConversation] = useState<File | null>(null);
  const [fichierMessage, setFichierMessage] = useState<File | null>(null);
  const [envoiEnCours, setEnvoiEnCours] = useState<EnvoiEnCours | null>(null);
  const messagesAvantEnvoiRef = useRef<Message[]>([]);

  const conversationQuery = useConversationQuery(conversationOuverteId);
  const creerConversationMutation = useCreerConversationMutation();
  const envoyerMessageMutation = useEnvoyerMessageMutation();

  // Une fois la frappe terminée, rebascule sur les données live dès qu'elles
  // contiennent bien ce tour (message + réponse), sans attendre davantage :
  // évite qu'une conversation déjà à jour reste figée sur l'état optimiste.
  useEffect(() => {
    if (envoiEnCours?.phase !== "termine") {
      return;
    }
    const messages = conversationQuery.data?.messages;
    if (messages && messages.length >= messagesAvantEnvoiRef.current.length + 2) {
      setEnvoiEnCours(null);
    }
  }, [envoiEnCours, conversationQuery.data]);

  function gererEnvoiNouvelleConversation(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();

    const message = champNouveauMessage;
    const fichier = fichierNouvelleConversation;
    if (!message.trim() || creerConversationMutation.isPending) {
      return;
    }
    creerConversationMutation.reset();

    messagesAvantEnvoiRef.current = [];
    setEnvoiEnCours({ message, phase: "attente", reponse: "" });
    setChampNouveauMessage("");

    creerConversationMutation.mutate(
      {
        message,
        fichier,
        cleIdempotence: crypto.randomUUID(),
      },
      {
        onSuccess: (donnees) => {
          setFichierNouvelleConversation(null);
          setEnvoiEnCours({ message, phase: "frappe", reponse: donnees.reponse });
          onConversationCreee(donnees.conversation.id);
        },
        onError: () => {
          setEnvoiEnCours(null);
          setChampNouveauMessage(message);
        },
      }
    );
  }

  function gererEnvoiMessage(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();

    const message = champMessage;
    const fichier = fichierMessage;
    if (!message.trim() || conversationOuverteId === null || envoyerMessageMutation.isPending) {
      return;
    }
    envoyerMessageMutation.reset();

    messagesAvantEnvoiRef.current = conversationQuery.data?.messages ?? [];
    setEnvoiEnCours({ message, phase: "attente", reponse: "" });
    setChampMessage("");

    envoyerMessageMutation.mutate(
      {
        conversationId: conversationOuverteId,
        message,
        fichier,
        cleIdempotence: crypto.randomUUID(),
      },
      {
        onSuccess: (donnees) => {
          setFichierMessage(null);
          setEnvoiEnCours({ message, phase: "frappe", reponse: donnees.reponse });
        },
        onError: () => {
          setEnvoiEnCours(null);
          setChampMessage(message);
        },
      }
    );
  }

  // Issue #84 : l'accroche ne s'affiche que si rien n'a encore été envoyé —
  // dès la soumission du premier message, on bascule sur le fil (avec les
  // bulles optimistes ci-dessous) sans attendre la réponse de la VM.
  const brouillonActif = conversationOuverteId === null && envoiEnCours === null;
  const messagesAffiches: Message[] =
    envoiEnCours !== null ? messagesAvantEnvoiRef.current : conversationQuery.data?.messages ?? [];

  const erreurConversationOuverte = messageErreur(
    conversationQuery.error,
    "L'ouverture de la conversation a échoué. Réessayez plus tard."
  );
  const erreurNouvelleConversation = messageErreur(
    creerConversationMutation.error,
    "La création de la conversation a échoué. Réessayez plus tard."
  );
  const erreurEnvoiMessage = messageErreur(
    envoyerMessageMutation.error,
    "L'envoi du message a échoué. Réessayez plus tard."
  );

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      {brouillonActif ? (
        <div className="flex flex-1 flex-col items-center justify-center">
          <div className="w-full max-w-2xl">
            <h2 className="mb-6 text-center text-2xl font-semibold tracking-tight">Comment puis-je vous aider ?</h2>
            <form onSubmit={gererEnvoiNouvelleConversation} className="flex flex-col gap-3">
              <ChampMessageAvecPieceJointe
                id="nouveau-message-conversation"
                label="Premier message"
                valeur={champNouveauMessage}
                onChange={setChampNouveauMessage}
                fichier={fichierNouvelleConversation}
                onFichierChange={setFichierNouvelleConversation}
                disabled={creerConversationMutation.isPending}
              />
              {creerConversationMutation.data?.pieceJointeEchecAnalyse && (
                <output className="text-sm text-muted-foreground">
                  L'IA n'a pas pu analyser la pièce jointe « {creerConversationMutation.data.pieceJointeNomFichier} ».
                </output>
              )}
              {erreurNouvelleConversation && (
                <p role="alert" className="text-sm text-destructive">
                  {erreurNouvelleConversation}
                </p>
              )}
            </form>
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <h2 className="mb-2 text-sm font-semibold">
            {conversationQuery.data?.titre ?? (conversationQuery.isLoading ? "Chargement…" : "")}
          </h2>
          {erreurConversationOuverte && (
            <p role="alert" className="mb-2 text-sm text-destructive">
              {erreurConversationOuverte}
            </p>
          )}
          <div role="log" className="mb-3 flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
            {messagesAffiches.map((message) =>
              message.role === "user" ? (
                <p
                  key={message.id}
                  className="self-end rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
                >
                  {message.contenu}
                </p>
              ) : (
                <div key={message.id} className="max-w-[70%] self-start rounded-md bg-muted px-3 py-1.5 text-sm">
                  <ContenuMessageAssistant texte={message.contenu} />
                </div>
              )
            )}
            {envoiEnCours && (
              <>
                <BulleMessageEnvoye texte={envoiEnCours.message} />
                {envoiEnCours.phase === "attente" ? (
                  <output className="flex max-w-[70%] items-center gap-2 self-start rounded-md bg-muted px-3 py-1.5 text-sm text-muted-foreground">
                    <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
                    Réflexion…
                  </output>
                ) : (
                  <div className="max-w-[70%] self-start rounded-md bg-muted px-3 py-1.5 text-sm">
                    <TexteAnimeReponse
                      texte={envoiEnCours.reponse}
                      onTermine={() =>
                        setEnvoiEnCours((precedent) => (precedent ? { ...precedent, phase: "termine" } : precedent))
                      }
                    />
                  </div>
                )}
              </>
            )}
          </div>

          <form onSubmit={gererEnvoiMessage} className="flex flex-col gap-3">
            <ChampMessageAvecPieceJointe
              id="message"
              label="Message"
              valeur={champMessage}
              onChange={setChampMessage}
              fichier={fichierMessage}
              onFichierChange={setFichierMessage}
              disabled={envoiEnCours !== null}
            />
            {envoyerMessageMutation.data?.pieceJointeEchecAnalyse && (
              <output className="text-sm text-muted-foreground">
                L'IA n'a pas pu analyser la pièce jointe « {envoyerMessageMutation.data.pieceJointeNomFichier} ».
              </output>
            )}
            {erreurEnvoiMessage && (
              <p role="alert" className="text-sm text-destructive">
                {erreurEnvoiMessage}
              </p>
            )}
          </form>
        </div>
      )}
    </div>
  );
}
