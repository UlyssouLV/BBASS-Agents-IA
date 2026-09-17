import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { appelApi, ErreurApi } from "@/lib/api";

// Même forme que poste.schemas.CompteResponse, plus l'avertissement de
// persistance dégradée que seule poste.schemas.ConnexionResponse porte (une
// restauration de session via /compte n'en a jamais).
export interface Compte {
  identifiant: string;
  prenom: string;
  nom: string;
  agence: string;
  poles: string[];
  est_admin: boolean;
  doit_changer_mot_de_passe: boolean;
  avertissement?: string | null;
}

const CLE_SESSION = ["session", "compte"] as const;

async function chargerCompteConnecte(): Promise<Compte | null> {
  try {
    return await appelApi<Compte>(
      "/compte",
      undefined,
      "Impossible de joindre le service de connexion. Réessayez plus tard.",
      "Impossible de récupérer le compte connecté."
    );
  } catch (erreur) {
    if (erreur instanceof ErreurApi && erreur.status === 401) {
      return null;
    }
    throw erreur;
  }
}

// Porte la logique de session qu'app.js gérait jusqu'ici par appels fetch
// directs (identifiant/jeton via les endpoints /connexion, /mot-de-passe,
// /deconnexion, /compte — mêmes routes, même contrat, voir docs/specs/
// v1.2.0-interface-poste.md). Le compte connecté vit dans le cache
// TanStack Query plutôt que dans un état local, pour que toute mutation qui
// le renvoie (connexion, changement de mot de passe) le mette à jour sans
// requête supplémentaire.
export function useSession() {
  const queryClient = useQueryClient();

  const compteQuery = useQuery({
    queryKey: CLE_SESSION,
    queryFn: chargerCompteConnecte,
    retry: false,
  });

  const connexion = useMutation({
    mutationFn: ({ identifiant, motDePasse }: { identifiant: string; motDePasse: string }) =>
      appelApi<Compte>(
        "/connexion",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ identifiant, mot_de_passe: motDePasse }),
        },
        "Impossible de joindre le service de connexion. Réessayez plus tard.",
        "La connexion a échoué. Réessayez plus tard."
      ),
    onSuccess: (compte) => {
      queryClient.setQueryData(CLE_SESSION, compte);
    },
  });

  const changerMotDePasse = useMutation({
    mutationFn: (nouveauMotDePasse: string) =>
      appelApi<Compte>(
        "/mot-de-passe",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nouveau_mot_de_passe: nouveauMotDePasse }),
        },
        "Impossible de joindre le service de connexion. Réessayez plus tard.",
        "Le changement de mot de passe a échoué. Réessayez plus tard."
      ),
    onSuccess: (compte) => {
      queryClient.setQueryData(CLE_SESSION, compte);
    },
    onError: (erreur) => {
      // Jeton devenu invalide entre-temps : même traitement que app.js
      // (afficherEcranConnexion sur un 401 pendant le changement de mot de
      // passe).
      if (erreur instanceof ErreurApi && erreur.status === 401) {
        queryClient.setQueryData(CLE_SESSION, null);
      }
    },
  });

  const deconnexion = useMutation({
    mutationFn: () =>
      appelApi<void>(
        "/deconnexion",
        { method: "POST" },
        "Impossible de joindre le service de connexion. Réessayez plus tard.",
        "La déconnexion a échoué."
      ),
    onSettled: () => {
      queryClient.setQueryData(CLE_SESSION, null);
    },
  });

  return {
    compte: compteQuery.data ?? null,
    chargementInitial: compteQuery.isLoading,
    connexion,
    changerMotDePasse,
    deconnexion,
  };
}
