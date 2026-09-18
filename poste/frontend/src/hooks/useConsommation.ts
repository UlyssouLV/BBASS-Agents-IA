import { useQuery, useQueryClient } from "@tanstack/react-query";

import { appelApi, ErreurApi } from "@/lib/api";
import { marquerSessionExpiree } from "@/hooks/useSession";

// Mêmes formes que poste.schemas (consommation.py) : DetailConsommationCategorieResponse
// (cout_usd sérialisé en chaîne, comme tout Decimal pydantic — voir
// test_consommation.py), ConversationConsommationResponse, ConsommationResponse.
export interface DetailConsommationCategorie {
  tokens_total: number;
  pages_traitees: number;
  cout_usd: string;
  nombre_requetes: number;
}

export interface ConversationConsommation {
  id: number;
  titre: string;
  cout_usd: string;
  chat: DetailConsommationCategorie;
  piece_jointe: DetailConsommationCategorie;
}

export interface Consommation {
  chat: DetailConsommationCategorie;
  piece_jointe: DetailConsommationCategorie;
  conversations: ConversationConsommation[];
}

const _MSG_ERREUR_RESEAU = "Impossible de joindre le service de consommation. Réessayez plus tard.";

async function chargerConsommation(): Promise<Consommation> {
  return appelApi<Consommation>(
    "/consommation",
    undefined,
    _MSG_ERREUR_RESEAU,
    "Le chargement de la consommation a échoué. Réessayez plus tard."
  );
}

// Porte la logique de la section #onglet-consommation d'app.js (voir
// docs/specs/v1.2.0-interface-poste.md) : total global (chat vs pièce
// jointe) et classement des conversations par coût décroissant — trié ici
// côté poste, la VM centrale renvoie les conversations sans ordre garanti.
export function useConsommationQuery() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["consommation"],
    queryFn: async () => {
      try {
        return await chargerConsommation();
      } catch (error_) {
        if (error_ instanceof ErreurApi && error_.status === 401) {
          marquerSessionExpiree(queryClient);
        }
        throw error_;
      }
    },
  });
}

export function conversationsParCoutDecroissant(conversations: ConversationConsommation[]): ConversationConsommation[] {
  return [...conversations].sort((a, b) => Number(b.cout_usd) - Number(a.cout_usd));
}
