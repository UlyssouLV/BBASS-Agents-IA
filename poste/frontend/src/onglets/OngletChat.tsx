import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  useConversationQuery,
  useConversationsQuery,
  useCreerConversationMutation,
  useEnvoyerMessageMutation,
  useRenommerConversationMutation,
  useSupprimerConversationMutation,
} from "@/hooks/useConversations";
import { ErreurApi } from "@/lib/api";

// Mêmes extensions/types qu'app.js (formulaireNouvelleConversation /
// formulaireChat) : la VM centrale n'accepte pas d'autres pièces jointes
// (spec 1.1.2).
const TYPES_PIECE_JOINTE_ACCEPTES = ".pdf,.docx,.xlsx,image/jpeg,image/png,image/webp,image/gif";

function messageErreur(erreur: unknown, messageParDefaut: string): string | null {
  if (!erreur) {
    return null;
  }
  return erreur instanceof ErreurApi ? erreur.message : messageParDefaut;
}

// Réécriture React de la section #onglet-chat d'app.js : liste des
// conversations à gauche, nouvelle conversation ou conversation ouverte à
// droite — même comportement qu'aujourd'hui (voir docs/specs/
// v1.2.0-interface-poste.md), porté sur les hooks TanStack Query de
// useConversations.ts (un hook mutation par action, invalidation du cache
// après chaque mutation plutôt qu'un état local dupliqué).
export function OngletChat() {
  const [conversationOuverteId, setConversationOuverteId] = useState<number | null>(null);
  const [champNouveauMessage, setChampNouveauMessage] = useState("");
  const [champMessage, setChampMessage] = useState("");
  const refFichierNouvelleConversation = useRef<HTMLInputElement>(null);
  const refFichierMessage = useRef<HTMLInputElement>(null);

  const conversationsQuery = useConversationsQuery();
  const conversationQuery = useConversationQuery(conversationOuverteId);
  const creerConversationMutation = useCreerConversationMutation();
  const envoyerMessageMutation = useEnvoyerMessageMutation();
  const renommerConversationMutation = useRenommerConversationMutation();
  const supprimerConversationMutation = useSupprimerConversationMutation();

  function afficherNouvelleConversation() {
    setConversationOuverteId(null);
  }

  function renommerConversation(id: number, titreActuel: string) {
    const nouveauTitre = window.prompt("Nouveau titre de la conversation :", titreActuel);
    if (!nouveauTitre || !nouveauTitre.trim() || nouveauTitre === titreActuel) {
      return;
    }
    renommerConversationMutation.mutate({ id, titre: nouveauTitre });
  }

  function supprimerConversation(id: number) {
    if (!window.confirm("Supprimer définitivement cette conversation ?")) {
      return;
    }
    supprimerConversationMutation.mutate(id, {
      onSuccess: () => {
        if (conversationOuverteId === id) {
          setConversationOuverteId(null);
        }
      },
    });
  }

  function gererEnvoiNouvelleConversation(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    creerConversationMutation.reset();

    const message = champNouveauMessage;
    if (!message.trim() || creerConversationMutation.isPending) {
      return;
    }

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
          setConversationOuverteId(donnees.conversation.id);
        },
      }
    );
  }

  function gererEnvoiMessage(evenement: FormEvent<HTMLFormElement>) {
    evenement.preventDefault();
    envoyerMessageMutation.reset();

    const message = champMessage;
    if (!message.trim() || conversationOuverteId === null || envoyerMessageMutation.isPending) {
      return;
    }

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

  const erreurConversations = messageErreur(
    conversationsQuery.error,
    "Le chargement des conversations a échoué. Réessayez plus tard."
  );
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
    <div className="flex gap-6">
      <div className="w-56 shrink-0">
        <h2 className="mb-2 text-sm font-semibold">Conversations</h2>
        {erreurConversations && (
          <p role="alert" className="mb-2 text-sm text-destructive">
            {erreurConversations}
          </p>
        )}
        <ul className="mb-3 flex flex-col gap-1">
          {conversationsQuery.data?.map((conversation) => (
            <li key={conversation.id} className="flex items-center gap-1">
              <button
                type="button"
                className="flex-1 truncate text-left text-sm hover:underline"
                onClick={() => setConversationOuverteId(conversation.id)}
              >
                {conversation.titre}
              </button>
              <button
                type="button"
                className="text-xs text-muted-foreground hover:underline"
                onClick={() => renommerConversation(conversation.id, conversation.titre)}
              >
                Renommer
              </button>
              <button
                type="button"
                className="text-xs text-destructive hover:underline"
                onClick={() => supprimerConversation(conversation.id)}
              >
                Supprimer
              </button>
            </li>
          ))}
        </ul>
        <Button type="button" variant="outline" size="sm" onClick={afficherNouvelleConversation}>
          Nouvelle conversation
        </Button>
      </div>

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
                <p role="status" className="text-sm text-muted-foreground">
                  L'IA n'a pas pu analyser la pièce jointe « {creerConversationMutation.data.pieceJointeNomFichier} ».
                </p>
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
            {envoyerMessageMutation.isPending && <p role="status">Envoi en cours…</p>}

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
                <p role="status" className="text-sm text-muted-foreground">
                  L'IA n'a pas pu analyser la pièce jointe « {envoyerMessageMutation.data.pieceJointeNomFichier} ».
                </p>
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
    </div>
  );
}
