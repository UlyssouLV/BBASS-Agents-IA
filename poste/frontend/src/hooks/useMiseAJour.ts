import { useQuery } from "@tanstack/react-query";

import { appelApi } from "@/lib/api";

// Même forme que poste.schemas.DerniereVerificationResponse : fichier d'état
// écrit par le Lanceur à chaque lancement (ADR-0022), null sans Lanceur.
export interface DerniereVerification {
  date: string;
  version_poste: string;
  version_serveur: string | null;
  resultat: "a_jour" | "mise_a_jour" | "echec" | "version_non_publiee";
  detail: string;
  bandeau: string | null;
}

async function chargerDerniereVerification(): Promise<DerniereVerification | null> {
  return appelApi<DerniereVerification | null>(
    "/mise-a-jour",
    undefined,
    "Impossible de lire l'état de la mise à jour.",
    "Impossible de lire l'état de la mise à jour."
  );
}

// Le Lanceur n'écrit ce fichier qu'au lancement : une lecture suffit.
export function useMiseAJour() {
  return useQuery({
    queryKey: ["mise-a-jour"],
    queryFn: chargerDerniereVerification,
    staleTime: Infinity,
    retry: false,
  });
}
