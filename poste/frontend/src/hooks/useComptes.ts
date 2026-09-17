import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { appelApi, ErreurApi } from "@/lib/api";
import { marquerSessionExpiree } from "@/hooks/useSession";
import type { DetailConsommationCategorie } from "@/hooks/useConsommation";

// Même forme que poste.schemas.CompteAdminResponse (routers/comptes.py) :
// vue admin d'un compte, avec email, sans le mot de passe.
export interface CompteAdmin {
  identifiant: string;
  prenom: string;
  nom: string;
  email: string | null;
  agence: string;
  poles: string[];
  est_admin: boolean;
  doit_changer_mot_de_passe: boolean;
}

// Même forme que poste.schemas.CompteCreeResponse : le mot de passe généré
// n'est renvoyé qu'à la création (voir OngletComptes, révélation en toast).
export interface CompteCree extends CompteAdmin {
  mot_de_passe: string;
}

const _MSG_ERREUR_RESEAU = "Impossible de joindre le service de gestion des comptes. Réessayez plus tard.";

export const CLE_COMPTES = ["comptes"] as const;

function _surErreurSession(queryClient: ReturnType<typeof useQueryClient>, erreur: unknown) {
  if (erreur instanceof ErreurApi && erreur.status === 401) {
    marquerSessionExpiree(queryClient);
  }
}

async function _chargerComptes(): Promise<CompteAdmin[]> {
  return appelApi<CompteAdmin[]>(
    "/comptes",
    undefined,
    _MSG_ERREUR_RESEAU,
    "Le chargement des comptes a échoué. Réessayez plus tard."
  );
}

// Même forme que poste.schemas.CompteConsommationResponse : détail agrégé
// par compte (chat/pièce jointe), jamais par conversation individuelle
// (confidentialité, spec 1.1.3/1.2.0) — classé par coût décroissant côté VM
// centrale (voir vm_centrale.routers.comptes.lister_consommation_comptes).
export interface CompteConsommation {
  identifiant: string;
  prenom: string;
  nom: string;
  cout_usd: string;
  chat: DetailConsommationCategorie;
  piece_jointe: DetailConsommationCategorie;
}

async function _chargerConsommationComptes(): Promise<CompteConsommation[]> {
  return appelApi<CompteConsommation[]>(
    "/comptes/consommation",
    undefined,
    _MSG_ERREUR_RESEAU,
    "Le chargement de la consommation des comptes a échoué. Réessayez plus tard."
  );
}

export function useComptesConsommationQuery() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["comptes", "consommation"],
    queryFn: async () => {
      try {
        return await _chargerConsommationComptes();
      } catch (erreur) {
        _surErreurSession(queryClient, erreur);
        throw erreur;
      }
    },
  });
}

export interface CreationCompteVariables {
  identifiant: string;
  prenom: string;
  nom: string;
  email: string | null;
  agence: string;
  poles: string[];
}

async function _creerCompte(variables: CreationCompteVariables): Promise<CompteCree> {
  return appelApi<CompteCree>(
    "/comptes",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(variables),
    },
    _MSG_ERREUR_RESEAU,
    "La création du compte a échoué. Réessayez plus tard."
  );
}

export interface ModificationCompteVariables {
  identifiant: string;
  prenom: string;
  nom: string;
  email: string | null;
  agence: string;
  poles: string[];
}

async function _modifierCompte({ identifiant, ...corps }: ModificationCompteVariables): Promise<CompteAdmin> {
  return appelApi<CompteAdmin>(
    `/comptes/${encodeURIComponent(identifiant)}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(corps),
    },
    _MSG_ERREUR_RESEAU,
    "La modification du compte a échoué. Réessayez plus tard."
  );
}

async function _reinitialiserMotDePasse(identifiant: string): Promise<{ mot_de_passe: string }> {
  return appelApi<{ mot_de_passe: string }>(
    `/comptes/${encodeURIComponent(identifiant)}/reinitialiser-mot-de-passe`,
    { method: "POST" },
    _MSG_ERREUR_RESEAU,
    "La réinitialisation du mot de passe a échoué. Réessayez plus tard."
  );
}

async function _deconnexionForcee(identifiant: string): Promise<void> {
  return appelApi<void>(
    `/comptes/${encodeURIComponent(identifiant)}/deconnexion-forcee`,
    { method: "POST" },
    _MSG_ERREUR_RESEAU,
    "La déconnexion forcée a échoué. Réessayez plus tard."
  );
}

export interface SuppressionCompteVariables {
  identifiant: string;
  cleAdminVm: string;
}

async function _supprimerCompte({ identifiant, cleAdminVm }: SuppressionCompteVariables): Promise<void> {
  return appelApi<void>(
    `/comptes/${encodeURIComponent(identifiant)}`,
    {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cle_admin_vm: cleAdminVm }),
    },
    _MSG_ERREUR_RESEAU,
    "La suppression du compte a échoué. Réessayez plus tard."
  );
}

export interface StatutAdminVariables {
  identifiant: string;
  estAdmin: boolean;
  cleAdminVm: string;
}

async function _modifierStatutAdmin({ identifiant, estAdmin, cleAdminVm }: StatutAdminVariables): Promise<CompteAdmin> {
  return appelApi<CompteAdmin>(
    `/comptes/${encodeURIComponent(identifiant)}/est-admin`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ est_admin: estAdmin, cle_admin_vm: cleAdminVm }),
    },
    _MSG_ERREUR_RESEAU,
    "Le changement de statut administrateur a échoué. Réessayez plus tard."
  );
}

// Porte la logique de l'onglet Comptes (admin) qu'app.js gérait par appels
// fetch directs (voir docs/specs/v1.2.0-interface-poste.md, Implementation
// Decisions — « TanStack Query ») : un hook par ressource, invalidation de
// la liste des comptes après chaque mutation qui la modifie.
export function useComptesQuery() {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: CLE_COMPTES,
    queryFn: async () => {
      try {
        return await _chargerComptes();
      } catch (erreur) {
        _surErreurSession(queryClient, erreur);
        throw erreur;
      }
    },
  });
}

export function useCreerCompteMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: _creerCompte,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CLE_COMPTES });
    },
    onError: (erreur) => _surErreurSession(queryClient, erreur),
  });
}

export function useModifierCompteMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: _modifierCompte,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CLE_COMPTES });
    },
    onError: (erreur) => _surErreurSession(queryClient, erreur),
  });
}

export function useReinitialiserMotDePasseMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: _reinitialiserMotDePasse,
    onError: (erreur) => _surErreurSession(queryClient, erreur),
  });
}

export function useDeconnexionForceeMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: _deconnexionForcee,
    onError: (erreur) => _surErreurSession(queryClient, erreur),
  });
}

export function useSupprimerCompteMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: _supprimerCompte,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CLE_COMPTES });
    },
    onError: (erreur) => _surErreurSession(queryClient, erreur),
  });
}

export function useModifierStatutAdminMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: _modifierStatutAdmin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CLE_COMPTES });
    },
    onError: (erreur) => _surErreurSession(queryClient, erreur),
  });
}
