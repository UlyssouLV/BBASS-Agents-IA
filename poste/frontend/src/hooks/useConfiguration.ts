import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { appelApi } from "@/lib/api";

// Mêmes formes que poste.schemas.ConfigurationResponse / EtatServeurBbassResponse
// (spec 1.6.2, point 9). hote vide : adresse inconnue, la Configuration
// s'ouvre d'elle-même. modifiable faux en dev : l'adresse vient du .env.
export interface Configuration {
  hote: string;
  port: number;
  modifiable: boolean;
}

export interface EtatServeurBbass {
  joignable: boolean;
  version: string | null;
}

export interface ServeurBbass {
  hote: string;
  port: number;
}

const _MSG_ERREUR_RESEAU = "Impossible de joindre le poste BBASS. Relancez BBASS.";
// Pastille : nouvel essai rapide tant que le Serveur BBASS est injoignable.
const _INTERVALLE_INJOIGNABLE = 5_000;
const _INTERVALLE_JOIGNABLE = 30_000;

function corpsJson(methode: string, corps: unknown): RequestInit {
  return { method: methode, headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) };
}

export function useEtatServeurBbass() {
  return useQuery({
    queryKey: ["serveur-bbass", "etat"],
    queryFn: () =>
      appelApi<EtatServeurBbass>("/serveur-bbass/etat", undefined, _MSG_ERREUR_RESEAU, _MSG_ERREUR_RESEAU),
    refetchInterval: (requete) => (requete.state.data?.joignable ? _INTERVALLE_JOIGNABLE : _INTERVALLE_INJOIGNABLE),
    retry: false,
  });
}

export function useConfiguration() {
  return useQuery({
    queryKey: ["configuration"],
    queryFn: () =>
      appelApi<Configuration>("/configuration", undefined, _MSG_ERREUR_RESEAU, "Impossible de lire la configuration."),
    staleTime: Infinity,
    retry: false,
  });
}

export function useTesterConnexion() {
  return useMutation({
    mutationFn: (serveur: ServeurBbass) =>
      appelApi<EtatServeurBbass>(
        "/configuration/test",
        corpsJson("POST", serveur),
        _MSG_ERREUR_RESEAU,
        "Adresse invalide : un hôte (nom ou adresse IP) et un port entre 1 et 65535."
      ),
  });
}

export function useEnregistrerConfiguration() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (serveur: ServeurBbass) =>
      appelApi<Configuration>(
        "/configuration",
        corpsJson("PUT", serveur),
        _MSG_ERREUR_RESEAU,
        "La configuration n'a pas pu être enregistrée."
      ),
    onSuccess: (configuration) => {
      queryClient.setQueryData(["configuration"], configuration);
      // Le chat relit l'adresse à chaque appel : la pastille aussi, tout de suite.
      void queryClient.invalidateQueries({ queryKey: ["serveur-bbass"] });
    },
  });
}

export function useOuvrirDossierConfiguration() {
  return useMutation({
    mutationFn: () =>
      appelApi<void>(
        "/configuration/ouvrir-dossier",
        { method: "POST" },
        _MSG_ERREUR_RESEAU,
        "Le dossier de configuration n'a pas pu être ouvert."
      ),
  });
}
