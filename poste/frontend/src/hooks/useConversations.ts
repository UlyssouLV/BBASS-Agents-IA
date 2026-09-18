import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { appelApi, ErreurApi } from "@/lib/api";
import { marquerSessionExpiree } from "@/hooks/useSession";

// Mêmes formes que poste.schemas (conversations.py) : voir
// ConversationResponse, ConversationDetailResponse, MessageResponse,
// PieceJointeResumeResponse, ConversationCreeResponse, MessageEnvoyeResponse.
export interface Conversation {
  id: number;
  titre: string;
  date_derniere_activite: string;
}

export interface Message {
  id: number;
  role: string;
  contenu: string;
  date_creation: string;
}

export interface ConversationDetail {
  id: number;
  titre: string;
  date_creation: string;
  date_derniere_activite: string;
  messages: Message[];
}

interface PieceJointeResume {
  id: number;
  nom_fichier: string;
  type_mime: string;
}

interface PieceJointeCreeeReponse {
  piece_jointe: PieceJointeResume;
  echec_analyse: boolean;
}

// Résultat d'une création de conversation ou d'un envoi de message : la
// pièce jointe éventuellement téléversée en amont (voir _envoyerPieceJointe)
// y est rattachée pour que l'appelant puisse afficher le même statut
// ponctuel qu'app.js (pieceJointeMessageStatut / pieceJointeNouvelleConversationStatut)
// sans dépendre d'un état local séparé.
interface ResultatPieceJointe {
  pieceJointeNomFichier: string | null;
  pieceJointeEchecAnalyse: boolean;
}

export interface ConversationCreee extends ResultatPieceJointe {
  conversation: { id: number; titre: string };
  reponse: string;
}

export interface MessageEnvoye extends ResultatPieceJointe {
  reponse: string;
}

const _MSG_ERREUR_RESEAU_CONVERSATIONS = "Impossible de joindre le service de conversations. Réessayez plus tard.";
const _MSG_ERREUR_RESEAU_PIECES_JOINTES = "Impossible de joindre le service de pièces jointes. Réessayez plus tard.";

export const CLE_CONVERSATIONS = ["conversations"] as const;

export function cleConversation(id: number) {
  return ["conversations", id] as const;
}

async function _envoyerPieceJointe(url: string, fichier: File): Promise<ResultatPieceJointe & { id: number }> {
  const donnees = new FormData();
  donnees.append("fichier", fichier);
  const cree = await appelApi<PieceJointeCreeeReponse>(
    url,
    { method: "POST", body: donnees },
    _MSG_ERREUR_RESEAU_PIECES_JOINTES,
    "L'envoi de la pièce jointe a échoué. Réessayez plus tard."
  );
  return {
    id: cree.piece_jointe.id,
    pieceJointeNomFichier: cree.piece_jointe.nom_fichier,
    pieceJointeEchecAnalyse: cree.echec_analyse,
  };
}

// Le fichier reste sélectionné dans l'input tant que la création de la
// conversation / l'envoi du message n'a pas réussi (voir OngletChat.tsx,
// vidé uniquement dans onSuccess) : un nouvel essai avec le même objet File
// doit réutiliser la pièce jointe déjà téléversée plutôt que d'en créer une
// seconde orpheline côté serveur si seul l'appel suivant avait échoué.
const _piecesEnCache = new WeakMap<File, Promise<ResultatPieceJointe & { id: number }>>();

function _envoyerPieceJointeAvecCache(url: string, fichier: File): Promise<ResultatPieceJointe & { id: number }> {
  const enCache = _piecesEnCache.get(fichier);
  if (enCache) {
    return enCache;
  }
  const promesse = _envoyerPieceJointe(url, fichier).catch((error_) => {
    _piecesEnCache.delete(fichier);
    throw error_;
  });
  _piecesEnCache.set(fichier, promesse);
  return promesse;
}

async function chargerConversations(): Promise<Conversation[]> {
  return appelApi<Conversation[]>(
    "/conversations",
    undefined,
    _MSG_ERREUR_RESEAU_CONVERSATIONS,
    "Le chargement des conversations a échoué. Réessayez plus tard."
  );
}

async function chargerConversation(id: number): Promise<ConversationDetail> {
  return appelApi<ConversationDetail>(
    `/conversations/${id}`,
    undefined,
    _MSG_ERREUR_RESEAU_CONVERSATIONS,
    "L'ouverture de la conversation a échoué. Réessayez plus tard."
  );
}

interface CreerConversationVariables {
  message: string;
  fichier: File | null;
  cleIdempotence: string;
}

async function creerConversation({
  message,
  fichier,
  cleIdempotence,
}: CreerConversationVariables): Promise<ConversationCreee> {
  const piece = fichier ? await _envoyerPieceJointeAvecCache("/pieces-jointes", fichier) : null;

  const cree = await appelApi<{ conversation: { id: number; titre: string }; reponse: string }>(
    "/conversations",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, cle_idempotence: cleIdempotence, piece_jointe_id: piece?.id ?? null }),
    },
    _MSG_ERREUR_RESEAU_CONVERSATIONS,
    "La création de la conversation a échoué. Réessayez plus tard."
  );

  return {
    ...cree,
    pieceJointeNomFichier: piece?.pieceJointeNomFichier ?? null,
    pieceJointeEchecAnalyse: piece?.pieceJointeEchecAnalyse ?? false,
  };
}

interface EnvoyerMessageVariables {
  conversationId: number;
  message: string;
  fichier: File | null;
  cleIdempotence: string;
}

async function envoyerMessage({
  conversationId,
  message,
  fichier,
  cleIdempotence,
}: EnvoyerMessageVariables): Promise<MessageEnvoye> {
  const piece = fichier
    ? await _envoyerPieceJointeAvecCache(`/conversations/${conversationId}/pieces-jointes`, fichier)
    : null;

  const envoi = await appelApi<{ reponse: string }>(
    `/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, cle_idempotence: cleIdempotence, piece_jointe_id: piece?.id ?? null }),
    },
    _MSG_ERREUR_RESEAU_CONVERSATIONS,
    "L'envoi du message a échoué. Réessayez plus tard."
  );

  return {
    ...envoi,
    pieceJointeNomFichier: piece?.pieceJointeNomFichier ?? null,
    pieceJointeEchecAnalyse: piece?.pieceJointeEchecAnalyse ?? false,
  };
}

async function renommerConversationRequete(id: number, titre: string): Promise<Conversation> {
  return appelApi<Conversation>(
    `/conversations/${id}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titre }),
    },
    _MSG_ERREUR_RESEAU_CONVERSATIONS,
    "Le renommage de la conversation a échoué. Réessayez plus tard."
  );
}

async function supprimerConversationRequete(id: number): Promise<void> {
  return appelApi<void>(
    `/conversations/${id}`,
    { method: "DELETE" },
    _MSG_ERREUR_RESEAU_CONVERSATIONS,
    "La suppression de la conversation a échoué. Réessayez plus tard."
  );
}

// Un 401 sur une query n'a pas d'équivalent à onError côté TanStack Query v5
// (retiré des useQuery) : chaque queryFn ci-dessous rattrape elle-même
// l'ErreurApi 401 pour faire basculer la session, avant de relayer l'erreur
// (React Query garde la query en erreur, sans conséquence puisque le compte
// vidé du cache démonte déjà EcranCompte — voir App.tsx).
function surErreurSession(queryClient: ReturnType<typeof useQueryClient>, erreur: unknown) {
  if (erreur instanceof ErreurApi && erreur.status === 401) {
    marquerSessionExpiree(queryClient);
  }
}

// Porte la logique de liste/ouverture/création/envoi/renommage/suppression
// de conversations qu'app.js gérait par appels fetch directs (voir
// docs/specs/v1.2.0-interface-poste.md, Implementation Decisions —
// « TanStack Query »). Un hook mutation par action (pas par appel HTTP) :
// une création ou un envoi englobe la pièce jointe optionnelle, comme dans
// l'unique gestionnaire de soumission d'app.js.
export function useConversationsQuery() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: CLE_CONVERSATIONS,
    queryFn: async () => {
      try {
        return await chargerConversations();
      } catch (error_) {
        surErreurSession(queryClient, error_);
        throw error_;
      }
    },
  });
}

export function useConversationQuery(id: number | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: cleConversation(id ?? -1),
    queryFn: async () => {
      try {
        return await chargerConversation(id as number);
      } catch (error_) {
        surErreurSession(queryClient, error_);
        throw error_;
      }
    },
    enabled: id !== null,
  });
}

export function useCreerConversationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: creerConversation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CLE_CONVERSATIONS });
    },
    onError: (erreur) => surErreurSession(queryClient, erreur),
  });
}

export function useEnvoyerMessageMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: envoyerMessage,
    onSuccess: (_donnees, variables) => {
      queryClient.invalidateQueries({ queryKey: cleConversation(variables.conversationId) });
      queryClient.invalidateQueries({ queryKey: CLE_CONVERSATIONS });
    },
    onError: (erreur) => surErreurSession(queryClient, erreur),
  });
}

export function useRenommerConversationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, titre }: { id: number; titre: string }) => renommerConversationRequete(id, titre),
    onSuccess: (_donnees, variables) => {
      queryClient.invalidateQueries({ queryKey: cleConversation(variables.id) });
      queryClient.invalidateQueries({ queryKey: CLE_CONVERSATIONS });
    },
    onError: (erreur) => surErreurSession(queryClient, erreur),
  });
}

export function useSupprimerConversationMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: supprimerConversationRequete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CLE_CONVERSATIONS });
    },
    onError: (erreur) => surErreurSession(queryClient, erreur),
  });
}
