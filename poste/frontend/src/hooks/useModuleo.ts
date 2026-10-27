import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { appelApi, ErreurApi } from "@/lib/api";
import { marquerSessionExpiree } from "@/hooks/useSession";

// Onglet Outils → Moduléo du Panel (spec 1.5.3, #213). Mêmes formes que
// vm_centrale.schemas (*Moduleo*), relayées telles quelles par
// poste.routers.moduleo.

export type ApplicationModuleo = "cogeo" | "planning";

// Une valeur par champ d'une condition Planning : `true` pour une case,
// { operateur, activites | groupes } pour « … des activités suivantes ».
export type ConditionsModuleo = Record<string, Record<string, unknown>>;

export interface DroitCatalogueModuleo {
  chemin: string;
  libelle: string;
  // Conditions que Moduléo propose sur l'action, avec leurs champs.
  conditions: Record<string, string[]> | null;
  sous_droits: DroitCatalogueModuleo[];
}

export interface CategorieDroitsModuleo {
  categorie: string;
  droits: DroitCatalogueModuleo[];
}

export type CatalogueModuleo = Record<ApplicationModuleo, CategorieDroitsModuleo[]>;

export interface GroupeModuleo {
  id: number;
  application: ApplicationModuleo;
  nom: string;
}

export interface DroitAccordeModuleo {
  chemin: string;
  conditions: ConditionsModuleo | null;
}

export interface RattachementModuleo {
  identifiant: string;
  groupe_cogeo_id: number | null;
  groupe_planning_id: number | null;
  id_utilisateur_moduleo: number | null;
}

// Champ absent : inchangé côté VM ; null : retiré.
export interface ModificationRattachementVariables {
  identifiant: string;
  groupe_cogeo_id?: number | null;
  groupe_planning_id?: number | null;
  utilisateur_moduleo?: string | null;
}

export interface EvenementJournalModuleo {
  date: string;
  admin: string;
  action: string;
  cible: string;
}

const _MSG_ERREUR_RESEAU = "Impossible de joindre le service d'administration Moduléo. Réessayez plus tard.";

const CLE_MODULEO = ["moduleo"] as const;
const CLE_GROUPES = ["moduleo", "groupes"] as const;
const CLE_RATTACHEMENTS = ["moduleo", "rattachements"] as const;
const CLE_JOURNAL = ["moduleo", "journal"] as const;

function _surErreurSession(queryClient: ReturnType<typeof useQueryClient>, erreur: unknown) {
  if (erreur instanceof ErreurApi && erreur.status === 401) {
    marquerSessionExpiree(queryClient);
  }
}

function _lire<T>(chemin: string, messageErreurParDefaut: string): Promise<T> {
  return appelApi<T>(`/moduleo/${chemin}`, undefined, _MSG_ERREUR_RESEAU, messageErreurParDefaut);
}

function _ecrire<T>(methode: string, chemin: string, corps: unknown, messageErreurParDefaut: string): Promise<T> {
  return appelApi<T>(
    `/moduleo/${chemin}`,
    {
      method: methode,
      headers: corps === undefined ? undefined : { "Content-Type": "application/json" },
      body: corps === undefined ? undefined : JSON.stringify(corps),
    },
    _MSG_ERREUR_RESEAU,
    messageErreurParDefaut
  );
}

function _useLecture<T>(cle: readonly unknown[], chemin: string, messageErreurParDefaut: string, active = true) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: cle,
    queryFn: async () => {
      try {
        return await _lire<T>(chemin, messageErreurParDefaut);
      } catch (error_) {
        _surErreurSession(queryClient, error_);
        throw error_;
      }
    },
    enabled: active,
  });
}

// Toute écriture réussie touche au journal : on invalide tout « moduleo »,
// sauf le catalogue, en lecture seule.
function _useEcriture<V, T>(ecrire: (variables: V) => Promise<T>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ecrire,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: CLE_MODULEO,
        predicate: (requete) => requete.queryKey[1] !== "catalogue",
      });
    },
    onError: (erreur) => _surErreurSession(queryClient, erreur),
  });
}

export function useCatalogueModuleoQuery() {
  return _useLecture<CatalogueModuleo>(
    ["moduleo", "catalogue"],
    "catalogue",
    "Le chargement du catalogue des droits Moduléo a échoué. Réessayez plus tard."
  );
}

export function useGroupesModuleoQuery() {
  return _useLecture<GroupeModuleo[]>(
    CLE_GROUPES,
    "groupes",
    "Le chargement des groupes Moduléo a échoué. Réessayez plus tard."
  );
}

export function useDroitsGroupeModuleoQuery(groupeId: number | null) {
  return _useLecture<DroitAccordeModuleo[]>(
    ["moduleo", "groupes", groupeId, "droits"],
    `groupes/${groupeId}/droits`,
    "Le chargement des droits du groupe a échoué. Réessayez plus tard.",
    groupeId !== null
  );
}

export function useRattachementsModuleoQuery() {
  return _useLecture<RattachementModuleo[]>(
    CLE_RATTACHEMENTS,
    "rattachements",
    "Le chargement des rattachements Moduléo a échoué. Réessayez plus tard."
  );
}

export function useJournalModuleoQuery() {
  return _useLecture<EvenementJournalModuleo[]>(
    CLE_JOURNAL,
    "journal",
    "Le chargement du journal des droits Moduléo a échoué. Réessayez plus tard."
  );
}

export function useCreerGroupeModuleoMutation() {
  return _useEcriture((variables: { application: ApplicationModuleo; nom: string }) =>
    _ecrire<GroupeModuleo>("POST", "groupes", variables, "La création du groupe a échoué. Réessayez plus tard.")
  );
}

export function useRenommerGroupeModuleoMutation() {
  return _useEcriture(({ id, nom }: { id: number; nom: string }) =>
    _ecrire<GroupeModuleo>("PATCH", `groupes/${id}`, { nom }, "Le renommage du groupe a échoué. Réessayez plus tard.")
  );
}

export function useSupprimerGroupeModuleoMutation() {
  return _useEcriture((id: number) =>
    _ecrire<void>("DELETE", `groupes/${id}`, undefined, "La suppression du groupe a échoué. Réessayez plus tard.")
  );
}

export function useRemplacerDroitsGroupeModuleoMutation() {
  return _useEcriture(({ id, droits }: { id: number; droits: DroitAccordeModuleo[] }) =>
    _ecrire<DroitAccordeModuleo[]>(
      "PUT",
      `groupes/${id}/droits`,
      droits,
      "L'enregistrement des droits du groupe a échoué. Réessayez plus tard."
    )
  );
}

export function useModifierRattachementModuleoMutation() {
  return _useEcriture(({ identifiant, ...corps }: ModificationRattachementVariables) =>
    _ecrire<RattachementModuleo>(
      "PATCH",
      `rattachements/${encodeURIComponent(identifiant)}`,
      corps,
      "La modification du rattachement a échoué. Réessayez plus tard."
    )
  );
}
