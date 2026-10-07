import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { appelApi, appelApiEnFlux, ErreurApi } from "@/lib/api";
import { marquerSessionExpiree } from "@/hooks/useSession";

// Mêmes formes que poste.schemas (conversations.py) : voir
// ConversationResponse, ConversationDetailResponse, MessageResponse,
// PieceJointeResumeResponse ; et vm_centrale.schemas ConversationCreeResponse,
// MessageEnvoyeResponse pour l'événement `fin` du flux d'un envoi (spec 1.4.4).
export interface Conversation {
  id: number;
  titre: string;
  date_derniere_activite: string;
}

// Jauge de contexte (spec 1.4.2) : prompt_tokens du dernier appel principal
// du tour (null pour un message `user` ou d'avant la 1.4.2) et fenêtre du
// modèle, toujours lue de la VM, jamais codée en dur ici.
interface JaugeContexte {
  tokens_contexte: number | null;
  fenetre_contexte: number;
}

export interface Message extends JaugeContexte {
  id: number;
  role: string;
  contenu: string;
  date_creation: string;
}

// Une page de la pagination par curseur de GET /conversations/{id} (issue
// #103) : `messages` y est toujours trié par ordre chronologique croissant,
// `a_des_messages_plus_anciens` indique s'il reste un historique plus ancien
// que cette page à charger (nouvel appel avec avant_id = id du premier
// message de cette page).
export interface ConversationDetailPage {
  id: number;
  titre: string;
  date_creation: string;
  date_derniere_activite: string;
  messages: Message[];
  a_des_messages_plus_anciens: boolean;
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

interface ConversationCreeeReponse extends JaugeContexte {
  conversation: { id: number; titre: string };
  reponse: string;
}

interface MessageEnvoyeReponse extends JaugeContexte {
  reponse: string;
}

export interface ConversationCreee extends ResultatPieceJointe, ConversationCreeeReponse {}

export interface MessageEnvoye extends ResultatPieceJointe, MessageEnvoyeReponse {}

const _MSG_ERREUR_RESEAU_CONVERSATIONS = "Impossible de joindre le service de conversations. Réessayez plus tard.";
const _MSG_ERREUR_RESEAU_PIECES_JOINTES = "Impossible de joindre le service de pièces jointes. Réessayez plus tard.";

export const CLE_CONVERSATIONS = ["conversations"] as const;

// Issue #101 : revue explicite par requête, au-delà du seul défaut global
// (main.tsx, staleTime: 30_000) — la liste reste invalidée immédiatement par
// ses propres mutations (création/renommage/suppression), ce délai ne joue
// donc que pour un changement externe pendant un aller-retour Chat <->
// Profil/Panel d'administration (la sidebar qui la porte est démontée dans
// ces deux vues, voir EcranCompte.tsx).
const _STALE_TIME_LISTE_CONVERSATIONS = 60_000;

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

async function chargerConversation(id: number, avantId?: number): Promise<ConversationDetailPage> {
  // avant_id absent sur le premier appel : la VM applique alors sa propre
  // fenêtre par défaut (spec 1.2.3) — jamais de valeur par défaut propre au
  // front ni de limite imposée ici.
  const parametres = avantId !== undefined ? `?avant_id=${avantId}` : "";
  return appelApi<ConversationDetailPage>(
    `/conversations/${id}${parametres}`,
    undefined,
    _MSG_ERREUR_RESEAU_CONVERSATIONS,
    "L'ouverture de la conversation a échoué. Réessayez plus tard."
  );
}

interface CreerConversationVariables {
  message: string;
  fichier: File | null;
  cleIdempotence: string;
  // Statut du tour (spec 1.4.4) : l'étape en cours, publiée par la VM.
  onStatut: (libelle: string) => void;
}

async function creerConversation({
  message,
  fichier,
  cleIdempotence,
  onStatut,
}: CreerConversationVariables): Promise<ConversationCreee> {
  const piece = fichier ? await _envoyerPieceJointeAvecCache("/pieces-jointes", fichier) : null;

  const cree = await appelApiEnFlux<ConversationCreeeReponse>(
    "/conversations",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, cle_idempotence: cleIdempotence, piece_jointe_id: piece?.id ?? null }),
    },
    onStatut,
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
  // Voir CreerConversationVariables.onStatut.
  onStatut: (libelle: string) => void;
}

async function envoyerMessage({
  conversationId,
  message,
  fichier,
  cleIdempotence,
  onStatut,
}: EnvoyerMessageVariables): Promise<MessageEnvoye> {
  const piece = fichier
    ? await _envoyerPieceJointeAvecCache(`/conversations/${conversationId}/pieces-jointes`, fichier)
    : null;

  const envoi = await appelApiEnFlux<MessageEnvoyeReponse>(
    `/conversations/${conversationId}/messages`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, cle_idempotence: cleIdempotence, piece_jointe_id: piece?.id ?? null }),
    },
    onStatut,
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
    staleTime: _STALE_TIME_LISTE_CONVERSATIONS,
  });
}

// Issue #103 : useInfiniteQuery plutôt que useQuery — chaque « page » est une
// fenêtre de GET /conversations/{id}, la première (pages[0]) étant toujours
// la plus récente (titre/dates de la conversation lus sur elle) et chaque
// fetchNextPage() en remontant une page plus ancienne (pageParam = id du
// premier message de la dernière page chargée). getNextPageParam renvoie
// undefined dès que cette dernière page n'a plus de message plus ancien
// (a_des_messages_plus_anciens) : TanStack Query expose alors hasNextPage à
// false, plus aucun fetchNextPage() ne se déclenche (voir OngletChat.tsx).
export function useConversationQuery(id: number | null) {
  const queryClient = useQueryClient();
  return useInfiniteQuery({
    queryKey: cleConversation(id ?? -1),
    queryFn: async ({ pageParam }) => {
      try {
        return await chargerConversation(id as number, pageParam);
      } catch (error_) {
        surErreurSession(queryClient, error_);
        throw error_;
      }
    },
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (dernierePage) =>
      dernierePage.a_des_messages_plus_anciens ? dernierePage.messages[0]?.id : undefined,
    enabled: id !== null,
    // Issue #101, étendu par la 1.2.3 : rebasculer vers une conversation
    // déjà visitée ne doit plus retomber sur un état vide / « Chargement… »
    // pendant le rechargement, même si son cache a expiré (gcTime) entre
    // deux visites — l'ancien contenu (celui de la conversation quittée)
    // reste affiché jusqu'à l'arrivée du nouveau, au lieu de disparaître dès
    // le changement de queryKey. Vaut aussi pour une conversation dont
    // plusieurs pages étaient déjà chargées : elles restent affichées, y
    // compris pendant qu'une bascule recharge la première page de la
    // nouvelle conversation.
    placeholderData: keepPreviousData,
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
