import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAPropos, useVerifierMaintenant } from "@/hooks/useAPropos";
import type { DerniereVerification } from "@/hooks/useMiseAJour";
import { messageErreur } from "@/lib/api";
import { cn } from "@/lib/utils";

// Le Lanceur rouvre la fenêtre sur /?a-propos&v=X.Y.Z après « Vérifier les mises
// à jour maintenant » (lanceur/coeur/src/lancement.rs, adresse_ouverte).
const _PARAMETRE_APRES_VERIFICATION = "a-propos";

const _RESULTATS: Record<DerniereVerification["resultat"], string> = {
  a_jour: "À jour",
  mise_a_jour: "Mise à jour réussie",
  echec: "Échec",
  version_non_publiee: "Version du serveur non publiée",
};

function formaterDate(date: string): string {
  const valeur = new Date(date);
  if (Number.isNaN(valeur.getTime())) {
    return date;
  }
  return valeur.toLocaleString("fr-FR", { dateStyle: "long", timeStyle: "short" });
}

interface DialogueAProposProps {
  ouvert: boolean;
  onOuvertChange: (ouvert: boolean) => void;
  // Ouvert par le Lanceur juste après une vérification : on dit ce qu'elle a donné.
  apresVerification?: boolean;
}

// À propos (spec 1.6.2, point 9) : versions du poste et de la VM, dernière
// vérification de mise à jour, et vérification à la demande.
export function DialogueAPropos({ ouvert, onOuvertChange, apresVerification = false }: Readonly<DialogueAProposProps>) {
  const aPropos = useAPropos(ouvert);
  const verifier = useVerifierMaintenant();
  const donnees = aPropos.data;
  const derniere = donnees?.derniere_verification ?? null;

  return (
    <Dialog open={ouvert} onOpenChange={onOuvertChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>À propos de BBASS</DialogTitle>
          <DialogDescription role={aPropos.error ? "alert" : undefined}>
            {donnees
              ? "Versions de ce poste et du Serveur BBASS auquel il est relié."
              : (messageErreur(aPropos.error, "Impossible de lire « À propos ».") ?? "Chargement…")}
          </DialogDescription>
        </DialogHeader>
        {donnees && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted-foreground">Version du poste</dt>
            <dd>{donnees.version_poste ? `v${donnees.version_poste}` : "Développement"}</dd>
            <dt className="text-muted-foreground">Version de la VM</dt>
            <dd>{donnees.version_serveur ? `v${donnees.version_serveur}` : "Serveur BBASS injoignable"}</dd>
            <dt className="text-muted-foreground">Dernière vérification</dt>
            <dd>
              {derniere ? (
                <>
                  <span className="block">{formaterDate(derniere.date)}</span>
                  <span
                    className={cn("block font-medium", derniere.resultat === "echec" ? "text-amber-700" : "text-emerald-700")}
                  >
                    {_RESULTATS[derniere.resultat] ?? derniere.resultat}
                  </span>
                  <span className="block text-muted-foreground">{derniere.detail}</span>
                </>
              ) : (
                "Aucune"
              )}
            </dd>
          </dl>
        )}
        {apresVerification && derniere?.resultat === "a_jour" && (
          <p role="status" className="text-sm font-medium text-emerald-700">
            Aucune nouvelle version : BBASS est déjà à jour, rien n'a été téléchargé.
          </p>
        )}
        {verifier.isSuccess && (
          <p role="status" className="text-sm font-medium">
            BBASS redémarre pour vérifier les mises à jour…
          </p>
        )}
        {verifier.error && (
          <p role="alert" className="text-sm text-destructive">
            {messageErreur(verifier.error, "La vérification des mises à jour n'a pas pu être lancée. Relancez BBASS.")}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOuvertChange(false)}>
            Fermer
          </Button>
          {donnees?.verification_possible && (
            <Button type="button" disabled={verifier.isPending || verifier.isSuccess} onClick={() => verifier.mutate()}>
              Vérifier les mises à jour maintenant
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Fenêtre rouverte par le Lanceur après une vérification : À propos s'ouvre
// sur son résultat, quel que soit l'écran (connexion ou chat).
export function AProposApresVerification() {
  const [ouvert, setOuvert] = useState(false);

  useEffect(() => {
    const url = new URL(globalThis.location.href);
    if (url.searchParams.has(_PARAMETRE_APRES_VERIFICATION)) {
      url.searchParams.delete(_PARAMETRE_APRES_VERIFICATION);
      globalThis.history.replaceState(null, "", url);
      setOuvert(true);
    }
  }, []);

  return <DialogueAPropos ouvert={ouvert} onOuvertChange={setOuvert} apresVerification />;
}
