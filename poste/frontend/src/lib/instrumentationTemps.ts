import { useEffect, useRef } from "react";

// Issue #102 : instrumentation de temps légère, désactivée par défaut, posée
// autour de l'ouverture/bascule d'une conversation, du chargement de la page
// Profil et du chargement du Panel d'administration — pensée pour être
// réutilisable telle quelle par l'inspecteur des échanges avec le modèle
// (1.3.0) sans construire son interface maintenant (voir docs/specs/
// v1.2.3-amelioration-delais-chargement.md).
//
// Le front est un build statique committé, sans étape de build sur le poste
// en production (voir vite.config.ts, ADR-0010) : une variable d'environnement
// Vite imposerait un rebuild pour (dés)activer la mesure, ce qu'un compte
// administrateur ne peut pas faire. Un indicateur localStorage joue le même
// rôle de « configuration, pas d'interface dédiée » tout en restant
// actionnable depuis la console du navigateur, par un développeur comme par
// un compte administrateur, sans rebuild.
const _CLE_LOCALSTORAGE = "bbass:instrumentation-temps";
const _PREFIXE_MESURE = "bbass:";

export function instrumentationTempsActive(): boolean {
  try {
    return localStorage.getItem(_CLE_LOCALSTORAGE) === "1";
  } catch {
    // localStorage indisponible (navigation privée stricte, etc.) :
    // l'instrumentation reste simplement désactivée.
    return false;
  }
}

function marquerDebutChargement(nom: string): void {
  if (!instrumentationTempsActive()) {
    return;
  }
  const nomMesure = `${_PREFIXE_MESURE}${nom}`;
  // Évite d'accumuler des marques/mesures sans fin sur une session poste qui
  // reste ouverte toute la journée (voir main.tsx) si le même point de
  // mesure est traversé plusieurs fois.
  performance.clearMarks(`${nomMesure}:debut`);
  performance.clearMeasures(nomMesure);
  performance.mark(`${nomMesure}:debut`);
}

function marquerFinChargement(nom: string): void {
  if (!instrumentationTempsActive()) {
    return;
  }
  const nomMesure = `${_PREFIXE_MESURE}${nom}`;
  try {
    const mesure = performance.measure(nomMesure, `${nomMesure}:debut`);
    // eslint-disable-next-line no-console
    console.info(`[instrumentation] ${nom} : ${Math.round(mesure.duration)} ms`);
  } catch {
    // Pas de marque de début correspondante (ex. instrumentation activée
    // après coup, en cours de chargement) : rien à mesurer, ignoré en
    // silence plutôt que de faire planter l'écran qui l'utilise.
  }
}

// Mesure le temps entre le premier rendu d'une page plein écran (Profil,
// Panel d'administration — montée/démontée à chaque navigation, voir
// EcranCompte.tsx) et le moment où `pret` devient vrai (ses requêtes de
// chargement ont abouti, en succès ou en erreur).
export function usePerfChargementPage(nom: string, pret: boolean): void {
  const marqueRef = useRef(false);
  if (!marqueRef.current) {
    marqueRef.current = true;
    marquerDebutChargement(nom);
  }

  const mesureeRef = useRef(false);
  useEffect(() => {
    if (pret && !mesureeRef.current) {
      mesureeRef.current = true;
      marquerFinChargement(nom);
    }
  });
}

// Mesure le temps entre un changement de `cle` (ex. l'identifiant de
// conversation ouverte, voir OngletChat.tsx) et le moment où `enCours`
// redevient faux — contrairement à usePerfChargementPage ci-dessus, le
// composant appelant reste monté d'une bascule à l'autre.
export function usePerfChargementParCle(nom: string, cle: unknown, enCours: boolean): void {
  const clePrecedenteRef = useRef(cle);
  const mesureeRef = useRef(true);

  if (clePrecedenteRef.current !== cle) {
    clePrecedenteRef.current = cle;
    mesureeRef.current = false;
    marquerDebutChargement(nom);
  }

  useEffect(() => {
    if (!enCours && !mesureeRef.current) {
      mesureeRef.current = true;
      marquerFinChargement(nom);
    }
  });
}
