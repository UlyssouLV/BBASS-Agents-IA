import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { File, FileImage, FileSpreadsheet, FileText, FileType, Paperclip, X, type LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useConversationQuery, useCreerConversationMutation, useEnvoyerMessageMutation } from "@/hooks/useConversations";
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

// Réécriture React de la section #onglet-chat d'app.js : ne porte plus que
// la conversation ouverte (nouvelle conversation ou fil existant) — la
// liste des conversations et sa création sont montées dans la sidebar
// permanente de l'écran Compte depuis le ticket #74 (voir
// BarreLaterale.tsx et docs/specs/v1.2.1-identite-visuelle-disposition.md),
// `conversationOuverteId` devenant un état partagé porté par EcranCompte.
// Issue #76 : écran de composition centré (accroche + textarea partagé) ;
// les mutations TanStack Query restent inchangées.
export function OngletChat({ conversationOuverteId, onConversationCreee }: Readonly<OngletChatProps>) {
  const [champNouveauMessage, setChampNouveauMessage] = useState("");
  const [champMessage, setChampMessage] = useState("");
  const [fichierNouvelleConversation, setFichierNouvelleConversation] = useState<File | null>(null);
  const [fichierMessage, setFichierMessage] = useState<File | null>(null);

  const conversationQuery = useConversationQuery(conversationOuverteId);
  const creerConversationMutation = useCreerConversationMutation();
  const envoyerMessageMutation = useEnvoyerMessageMutation();

  function gererEnvoiNouvelleConversation(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();

    const message = champNouveauMessage;
    if (!message.trim() || creerConversationMutation.isPending) {
      return;
    }
    creerConversationMutation.reset();

    creerConversationMutation.mutate(
      {
        message,
        fichier: fichierNouvelleConversation,
        cleIdempotence: crypto.randomUUID(),
      },
      {
        onSuccess: (donnees) => {
          setChampNouveauMessage("");
          setFichierNouvelleConversation(null);
          onConversationCreee(donnees.conversation.id);
        },
      }
    );
  }

  function gererEnvoiMessage(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();

    const message = champMessage;
    if (!message.trim() || conversationOuverteId === null || envoyerMessageMutation.isPending) {
      return;
    }
    envoyerMessageMutation.reset();

    envoyerMessageMutation.mutate(
      {
        conversationId: conversationOuverteId,
        message,
        fichier: fichierMessage,
        cleIdempotence: crypto.randomUUID(),
      },
      {
        onSuccess: () => {
          setChampMessage("");
          setFichierMessage(null);
        },
      }
    );
  }

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
      {conversationOuverteId === null ? (
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
              <Button type="submit" disabled={creerConversationMutation.isPending} className="self-start">
                Envoyer
              </Button>
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
            {conversationQuery.data?.messages.map((message) => (
              <p
                key={message.id}
                className={
                  message.role === "user"
                    ? "self-end rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground"
                    : "self-start rounded-md bg-muted px-3 py-1.5 text-sm"
                }
              >
                {message.contenu}
              </p>
            ))}
          </div>
          {envoyerMessageMutation.isPending && <output className="block">Envoi en cours…</output>}

          <form onSubmit={gererEnvoiMessage} className="flex flex-col gap-3">
            <ChampMessageAvecPieceJointe
              id="message"
              label="Message"
              valeur={champMessage}
              onChange={setChampMessage}
              fichier={fichierMessage}
              onFichierChange={setFichierMessage}
              disabled={envoyerMessageMutation.isPending}
            />
            <Button type="submit" disabled={envoyerMessageMutation.isPending} className="self-start">
              Envoyer
            </Button>
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
