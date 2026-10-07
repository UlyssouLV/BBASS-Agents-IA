import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useCreerConversationMutation, useEnvoyerMessageMutation, type Message } from "@/hooks/useConversations";

// Issue #166 : l'envoi en cours n'est plus un état unique d'OngletChat mais
// un état **par conversation**, tenu par EcranCompte pour survivre à une
// bascule (et au démontage de l'onglet vers Profil / Panel
// d'administration). Clé = id de la conversation, ou « nouvelle » pour un
// premier message tant que la VM n'a pas renvoyé l'id (la vue « Nouvelle
// conversation » garde alors cet envoi, voir OngletChat.tsx).
export type CleEnvoi = number | "nouvelle";

export function cleEnvoi(conversationId: number | null): CleEnvoi {
  return conversationId ?? "nouvelle";
}

// Phases d'un envoi (issue #84) :
// - "attente" : la VM n'a pas encore répondu ; affiche le dernier statut
//   du tour reçu (spec 1.4.4), « Réflexion… » avant le premier.
// - "frappe"  : la réponse est connue et s'écrit progressivement (voir
//   TexteAnimeReponse dans OngletChat.tsx).
// - "termine" : la réponse est affichée en entier ; on attend que la
//   conversation (invalidée par la mutation) rattrape le nouveau tour avant
//   de rebasculer sur ses données. Une réponse arrivée pendant qu'on regarde
//   une autre conversation, ou une frappe quittée en cours, passe
//   directement ici : pas d'animation au retour.
export type PhaseEnvoi = "attente" | "frappe" | "termine";

export interface EnvoiEnCours {
  message: string;
  phase: PhaseEnvoi;
  reponse: string;
  statut: string;
  // Liste affichée figée au moment de l'envoi (vide pour une nouvelle
  // conversation) : tant que l'envoi existe, le fil se construit à partir de
  // ce figé + des bulles optimistes plutôt que des données live.
  messagesAvant: Message[];
  // Titre renvoyé par la création, tant que la conversation n'est pas
  // chargée (issue #127).
  titre?: string;
}

// Ce qu'un envoi terminé laisse à afficher sous le champ de sa conversation.
// `aRestaurer` : message (et pièce jointe, même objet File pour réutiliser
// le téléversement déjà fait, voir useConversations.ts) à remettre dans le
// champ après un échec — appliqué par OngletChat à l'ouverture de la
// conversation concernée, même si l'échec est arrivé ailleurs.
export interface RetourEnvoi {
  erreur: unknown;
  aRestaurer: { message: string; fichier: File | null } | null;
  pieceJointeNonAnalysee: string | null;
}

const _STATUT_INITIAL = "Réflexion…";

function avec<V>(carte: ReadonlyMap<CleEnvoi, V>, cle: CleEnvoi, valeur: V | undefined): Map<CleEnvoi, V> {
  const suivante = new Map(carte);
  if (valeur === undefined) {
    suivante.delete(cle);
  } else {
    suivante.set(cle, valeur);
  }
  return suivante;
}

export function useEnvoisEnCours(
  conversationOuverteId: number | null,
  onConversationCreee: (id: number, ouverte: boolean) => void
) {
  const [envois, setEnvois] = useState<ReadonlyMap<CleEnvoi, EnvoiEnCours>>(new Map());
  const [retours, setRetours] = useState<ReadonlyMap<CleEnvoi, RetourEnvoi>>(new Map());
  const creerConversationMutation = useCreerConversationMutation();
  const envoyerMessageMutation = useEnvoyerMessageMutation();

  // Lus à la fin d'un envoi, qui peut arriver bien après la soumission :
  // toujours la conversation ouverte et le rappel courants.
  const cleOuverte = cleEnvoi(conversationOuverteId);
  const cleOuverteRef = useRef(cleOuverte);
  cleOuverteRef.current = cleOuverte;
  const onConversationCreeeRef = useRef(onConversationCreee);
  onConversationCreeeRef.current = onConversationCreee;

  // Une frappe quittée en cours ne reprend pas au retour : son
  // TexteAnimeReponse est démonté, elle passe à « termine ».
  useEffect(() => {
    setEnvois((precedents) => {
      const aTerminer = [...precedents].filter(([cle, envoi]) => cle !== cleOuverte && envoi.phase === "frappe");
      if (aTerminer.length === 0) {
        return precedents;
      }
      const suivants = new Map(precedents);
      for (const [cle, envoi] of aTerminer) {
        suivants.set(cle, { ...envoi, phase: "termine" });
      }
      return suivants;
    });
  }, [cleOuverte]);

  const mettreAJour = useCallback((cle: CleEnvoi, maj: (envoi: EnvoiEnCours) => EnvoiEnCours | undefined) => {
    setEnvois((precedents) => {
      const envoi = precedents.get(cle);
      return envoi ? avec(precedents, cle, maj(envoi)) : precedents;
    });
  }, []);

  const terminerFrappe = useCallback(
    (cle: CleEnvoi) =>
      mettreAJour(cle, (envoi) => (envoi.phase === "frappe" ? { ...envoi, phase: "termine" } : envoi)),
    [mettreAJour]
  );

  const oublierEnvoi = useCallback((cle: CleEnvoi) => mettreAJour(cle, () => undefined), [mettreAJour]);

  const consommerRestauration = useCallback((cle: CleEnvoi) => {
    setRetours((precedents) => {
      const retour = precedents.get(cle);
      return retour?.aRestaurer ? avec(precedents, cle, { ...retour, aRestaurer: null }) : precedents;
    });
  }, []);

  function demarrer(cle: CleEnvoi, message: string, messagesAvant: Message[]) {
    setRetours((precedents) => avec(precedents, cle, undefined));
    setEnvois((precedents) =>
      avec(precedents, cle, { message, phase: "attente", reponse: "", statut: _STATUT_INITIAL, messagesAvant })
    );
    return (libelle: string) =>
      mettreAJour(cle, (envoi) => (envoi.phase === "attente" ? { ...envoi, statut: libelle } : envoi));
  }

  function echouer(cle: CleEnvoi, erreur: unknown, message: string, fichier: File | null) {
    setEnvois((precedents) => avec(precedents, cle, undefined));
    setRetours((precedents) =>
      avec(precedents, cle, { erreur, aRestaurer: { message, fichier }, pieceJointeNonAnalysee: null })
    );
  }

  function retourSucces(pieceJointeEchecAnalyse: boolean, pieceJointeNomFichier: string | null): RetourEnvoi {
    return {
      erreur: null,
      aRestaurer: null,
      pieceJointeNonAnalysee: pieceJointeEchecAnalyse ? pieceJointeNomFichier : null,
    };
  }

  // mutateAsync plutôt que les rappels de mutate() : ceux-ci ne partent que
  // pour le dernier appel d'un même useMutation, et plus du tout une fois le
  // composant démonté — or plusieurs conversations peuvent avoir un tour en
  // vol en même temps.
  async function envoyerPremierMessage(message: string, fichier: File | null) {
    const onStatut = demarrer("nouvelle", message, []);
    try {
      const donnees = await creerConversationMutation.mutateAsync({
        message,
        fichier,
        cleIdempotence: crypto.randomUUID(),
        onStatut,
      });
      const id = donnees.conversation.id;
      const ouverte = cleOuverteRef.current === "nouvelle";
      setEnvois((precedents) => {
        const suivants = avec(precedents, "nouvelle", undefined);
        suivants.set(id, {
          message,
          phase: ouverte ? "frappe" : "termine",
          reponse: donnees.reponse,
          statut: "",
          messagesAvant: [],
          titre: donnees.conversation.titre,
        });
        return suivants;
      });
      setRetours((precedents) =>
        avec(precedents, id, retourSucces(donnees.pieceJointeEchecAnalyse, donnees.pieceJointeNomFichier))
      );
      onConversationCreeeRef.current(id, ouverte);
    } catch (erreur) {
      echouer("nouvelle", erreur, message, fichier);
    }
  }

  async function envoyerMessage(conversationId: number, message: string, fichier: File | null, messagesAvant: Message[]) {
    const onStatut = demarrer(conversationId, message, messagesAvant);
    try {
      const donnees = await envoyerMessageMutation.mutateAsync({
        conversationId,
        message,
        fichier,
        cleIdempotence: crypto.randomUUID(),
        onStatut,
      });
      const ouverte = cleOuverteRef.current === conversationId;
      mettreAJour(conversationId, (envoi) => ({
        ...envoi,
        phase: ouverte ? "frappe" : "termine",
        reponse: donnees.reponse,
        statut: "",
      }));
      setRetours((precedents) =>
        avec(precedents, conversationId, retourSucces(donnees.pieceJointeEchecAnalyse, donnees.pieceJointeNomFichier))
      );
    } catch (erreur) {
      echouer(conversationId, erreur, message, fichier);
    }
  }

  // Indicateur de la sidebar : une conversation dont le tour est en vol
  // (retiré à `fin` comme à `erreur`).
  const conversationsEnAttente = useMemo(
    () =>
      new Set(
        [...envois]
          .filter(([cle, envoi]) => cle !== "nouvelle" && envoi.phase === "attente")
          .map(([cle]) => cle as number)
      ),
    [envois]
  );

  return {
    envois,
    retours,
    conversationsEnAttente,
    envoyerPremierMessage,
    envoyerMessage,
    terminerFrappe,
    oublierEnvoi,
    consommerRestauration,
  };
}

export type EnvoisEnCours = ReturnType<typeof useEnvoisEnCours>;
