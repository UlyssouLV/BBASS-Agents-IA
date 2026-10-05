import { useQuery, useQueryClient } from "@tanstack/react-query";

import { appelApi, ErreurApi } from "@/lib/api";
import { marquerSessionExpiree } from "@/hooks/useSession";

// Même forme que poste.schemas.ProfilTravailResponse : contenu vide ("")
// signifie « aucun profil enregistré », comme dans app.js (chargerProfilTravail).
export interface ProfilTravail {
  contenu: string;
  date_derniere_maj: string | null;
}

const _MSG_ERREUR_RESEAU = "Impossible de joindre le service de profil de travail. Réessayez plus tard.";

// Issue #101 : revue explicite par requête, au-delà du seul défaut global
// (main.tsx, staleTime: 30_000) — contenu renseigné manuellement et modifié
// rarement, un aller-retour Chat <-> Profil (qui démonte cette requête, voir
// EcranCompte.tsx) ne doit pas déclencher de rafraîchissement visible.
const _STALE_TIME_PROFIL_TRAVAIL = 5 * 60_000;

async function chargerProfilTravail(): Promise<ProfilTravail> {
  return appelApi<ProfilTravail>(
    "/profil-travail",
    undefined,
    _MSG_ERREUR_RESEAU,
    "Le chargement du profil de travail a échoué. Réessayez plus tard."
  );
}

// Porte la logique de la section #onglet-profil-travail d'app.js (voir
// docs/specs/v1.2.0-interface-poste.md) : lecture seule, aucune mutation.
export function useProfilTravailQuery() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["profil-travail"],
    queryFn: async () => {
      try {
        return await chargerProfilTravail();
      } catch (error_) {
        if (error_ instanceof ErreurApi && error_.status === 401) {
          marquerSessionExpiree(queryClient);
        }
        throw error_;
      }
    },
    staleTime: _STALE_TIME_PROFIL_TRAVAIL,
  });
}
