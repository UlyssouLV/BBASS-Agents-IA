import { useMutation, useQuery } from "@tanstack/react-query";

import { appelApi } from "@/lib/api";
import type { DerniereVerification } from "@/hooks/useMiseAJour";

// Même forme que poste.schemas.AProposResponse (spec 1.6.2, point 9).
// version_poste nulle en dev (pas de Lanceur), version_serveur nulle si le
// Serveur BBASS est injoignable.
export interface APropos {
  version_poste: string | null;
  version_serveur: string | null;
  derniere_verification: DerniereVerification | null;
  verification_possible: boolean;
}

const _MSG_ERREUR_RESEAU = "Impossible de joindre le poste BBASS. Relancez BBASS.";

// Lu à chaque ouverture : la version de la VM peut avoir changé depuis.
export function useAPropos(actif: boolean) {
  return useQuery({
    queryKey: ["a-propos"],
    queryFn: () => appelApi<APropos>("/a-propos", undefined, _MSG_ERREUR_RESEAU, "Impossible de lire « À propos »."),
    enabled: actif,
    staleTime: 0,
    retry: false,
  });
}

// Le Lanceur redémarre BBASS en mode vérification puis rouvre la fenêtre sur À propos.
export function useVerifierMaintenant() {
  return useMutation({
    mutationFn: () =>
      appelApi<void>(
        "/mise-a-jour/verifier",
        { method: "POST" },
        _MSG_ERREUR_RESEAU,
        "La vérification des mises à jour n'a pas pu être lancée. Relancez BBASS."
      ),
  });
}
