import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useConversationQuery, useCreerConversationMutation, useEnvoyerMessageMutation } from "@/hooks/useConversations";
import { messageErreur } from "@/lib/api";

// Mêmes extensions/types qu'app.js (formulaireNouvelleConversation /
// formulaireChat) : la VM centrale n'accepte pas d'autres pièces jointes
// (spec 1.1.2).
const TYPES_PIECE_JOINTE_ACCEPTES = ".pdf,.docx,.xlsx,image/jpeg,image/png,image/webp,image/gif";

interface OngletChatProps {
  conversationOuverteId: number | null;
  onConversationCreee: (id: number) => void;
}

// Réécriture React de la section #onglet-chat d'app.js : ne porte plus que
// la conversation ouverte (nouvelle conversation ou fil existant) — la
// liste des conversations et sa création sont montées dans la sidebar
// permanente de l'écran Compte depuis le ticket #74 (voir
// BarreLaterale.tsx et docs/specs/v1.2.1-identite-visuelle-disposition.md),
// `conversationOuverteId` devenant un état partagé porté par EcranCompte.
// Même comportement qu'auparavant, porté sur les hooks TanStack Query de
// useConversations.ts (un hook mutation par action, invalidation du cache
// après chaque mutation plutôt qu'un état local dupliqué).
export function OngletChat({ conversationOuverteId, onConversationCreee }: Readonly<OngletChatProps>) {
  const [champNouveauMessage, setChampNouveauMessage] = useState("");
  const [champMessage, setChampMessage] = useState("");
  const refFichierNouvelleConversation = useRef<HTMLInputElement>(null);
  const refFichierMessage = useRef<HTMLInputElement>(null);

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
        fichier: refFichierNouvelleConversation.current?.files?.[0] ?? null,
        cleIdempotence: crypto.randomUUID(),
      },
      {
        onSuccess: (donnees) => {
          setChampNouveauMessage("");
          if (refFichierNouvelleConversation.current) {
            refFichierNouvelleConversation.current.value = "";
          }
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
        fichier: refFichierMessage.current?.files?.[0] ?? null,
        cleIdempotence: crypto.randomUUID(),
      },
      {
        onSuccess: () => {
          setChampMessage("");
          if (refFichierMessage.current) {
            refFichierMessage.current.value = "";
          }
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
    <div className="min-w-0 flex-1">
      {conversationOuverteId === null ? (
          <div>
            <h2 className="mb-2 text-sm font-semibold">Nouvelle conversation</h2>
            <form onSubmit={gererEnvoiNouvelleConversation} className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="nouveau-message-conversation" className="sr-only">
                  Premier message
                </Label>
                <Input
                  id="nouveau-message-conversation"
                  autoComplete="off"
                  required
                  value={champNouveauMessage}
                  onChange={(evenement) => setChampNouveauMessage(evenement.target.value)}
                  disabled={creerConversationMutation.isPending}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="piece-jointe-nouvelle-conversation">Pièce jointe (optionnel)</Label>
                <Input
                  id="piece-jointe-nouvelle-conversation"
                  type="file"
                  accept={TYPES_PIECE_JOINTE_ACCEPTES}
                  ref={refFichierNouvelleConversation}
                  disabled={creerConversationMutation.isPending}
                />
              </div>
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
        ) : (
          <div>
            <h2 className="mb-2 text-sm font-semibold">
              {conversationQuery.data?.titre ?? (conversationQuery.isLoading ? "Chargement…" : "")}
            </h2>
            {erreurConversationOuverte && (
              <p role="alert" className="mb-2 text-sm text-destructive">
                {erreurConversationOuverte}
              </p>
            )}
            <div role="log" className="mb-3 flex flex-col gap-2">
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
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="message" className="sr-only">
                  Message
                </Label>
                <Input
                  id="message"
                  autoComplete="off"
                  required
                  value={champMessage}
                  onChange={(evenement) => setChampMessage(evenement.target.value)}
                  disabled={envoyerMessageMutation.isPending}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="piece-jointe-message">Pièce jointe (optionnel)</Label>
                <Input
                  id="piece-jointe-message"
                  type="file"
                  accept={TYPES_PIECE_JOINTE_ACCEPTES}
                  ref={refFichierMessage}
                  disabled={envoyerMessageMutation.isPending}
                />
              </div>
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
