import { useQuery } from "@tanstack/react-query";

import { appelApi } from "@/lib/api";

// Mêmes formes que poste.schemas.Inspecteur*Response (routers/inspecteur.py,
// spec 1.3.0) : lecture seule des échanges capturés avec Mistral.
export interface InspecteurCompte {
  identifiant_compte: string;
}

export interface InspecteurConversation {
  id: number;
  titre: string;
  date_creation: string;
  date_derniere_activite: string;
}

export interface InspecteurEchangeResume {
  id: number;
  type_appel: string;
  statut: string;
  date_creation: string;
}

export interface InspecteurEchangeDetail extends InspecteurEchangeResume {
  identifiant_compte: string;
  conversation_id: number | null;
  piece_jointe_id: number | null;
  modele: string;
  requete_payload: Record<string, unknown>;
  reponse_payload: Record<string, unknown> | null;
  erreur: string | null;
}

const _MSG_ERREUR_RESEAU = "Impossible de joindre le service de l'inspecteur. Réessayez plus tard.";

// Préfixe commun des clés de requête : PageInspecteur les retire toutes d'un
// coup quand la Clé d'administration VM est ressaisie.
export const CLE_INSPECTEUR = ["inspecteur"] as const;

// Historique seulement, rafraîchi manuellement (spec 1.3.0) : jamais de
// refetch implicite (focus fenêtre, délai écoulé), seulement le bouton
// « Rafraîchir » de chaque niveau.
const _OPTIONS_HISTORIQUE = {
  staleTime: Infinity,
  refetchOnWindowFocus: false,
  retry: false,
} as const;

// La Clé d'administration VM n'est jamais dans la clé de requête ni stockée
// ailleurs qu'en mémoire de PageInspecteur : elle n'est passée qu'en en-tête
// X-Admin-Key, que poste relaie tel quel à la VM centrale.
function _chargerInspecteur<T>(chemin: string, cleAdminVm: string, messageParDefaut: string): Promise<T> {
  return appelApi<T>(chemin, { headers: { "X-Admin-Key": cleAdminVm } }, _MSG_ERREUR_RESEAU, messageParDefaut);
}

export function useInspecteurComptesQuery(cleAdminVm: string) {
  return useQuery({
    queryKey: [...CLE_INSPECTEUR, "comptes"],
    queryFn: () =>
      _chargerInspecteur<InspecteurCompte[]>(
        "/inspecteur/comptes",
        cleAdminVm,
        "Le chargement des comptes a échoué. Réessayez plus tard."
      ),
    ..._OPTIONS_HISTORIQUE,
  });
}

export function useInspecteurConversationsQuery(cleAdminVm: string, identifiantCompte: string) {
  return useQuery({
    queryKey: [...CLE_INSPECTEUR, "comptes", identifiantCompte, "conversations"],
    queryFn: () =>
      _chargerInspecteur<InspecteurConversation[]>(
        `/inspecteur/comptes/${encodeURIComponent(identifiantCompte)}/conversations`,
        cleAdminVm,
        "Le chargement des conversations a échoué. Réessayez plus tard."
      ),
    ..._OPTIONS_HISTORIQUE,
  });
}

export function useInspecteurEchangesQuery(cleAdminVm: string, conversationId: number) {
  return useQuery({
    queryKey: [...CLE_INSPECTEUR, "conversations", conversationId, "echanges"],
    queryFn: () =>
      _chargerInspecteur<InspecteurEchangeResume[]>(
        `/inspecteur/conversations/${conversationId}/echanges`,
        cleAdminVm,
        "Le chargement des échanges a échoué. Réessayez plus tard."
      ),
    ..._OPTIONS_HISTORIQUE,
  });
}

// Détail chargé seulement quand la carte d'échange est dépliée : le payload
// peut porter le texte intégral d'une pièce jointe ou un fichier en base64.
export function useInspecteurEchangeQuery(cleAdminVm: string, echangeId: number, actif: boolean) {
  return useQuery({
    queryKey: [...CLE_INSPECTEUR, "echanges", echangeId],
    queryFn: () =>
      _chargerInspecteur<InspecteurEchangeDetail>(
        `/inspecteur/echanges/${echangeId}`,
        cleAdminVm,
        "Le chargement de l'échange a échoué. Réessayez plus tard."
      ),
    enabled: actif,
    ..._OPTIONS_HISTORIQUE,
  });
}
