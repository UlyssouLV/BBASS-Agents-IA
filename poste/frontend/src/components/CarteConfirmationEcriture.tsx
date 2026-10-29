import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useDeciderEcritureMutation, type CarteEcriture } from "@/hooks/useConversations";
import { messageErreur } from "@/lib/api";
import { cn } from "@/lib/utils";

// Carte de confirmation d'une écriture Moduléo (spec 1.5.2, #204) : ce que
// le modèle propose d'écrire, en noms, et deux boutons traités par la VM,
// hors du modèle. Un « oui » tapé dans le chat ne confirme rien. Style
// provisoire, revu avec les Agents par pôle. PUT (#205) : la fiche de
// l'élément visé (#253), puis « ancien → nouveau » des seuls champs
// modifiés ; DELETE : la fiche sous « Sera supprimé ».
//
// `desactivee` : tant que le tour qui l'a proposée n'est pas fini, la carte
// n'est pas encore en base côté VM.
export function CarteConfirmationEcriture({
  carte,
  conversationId,
  desactivee = false,
}: Readonly<{ carte: CarteEcriture; conversationId: number | null; desactivee?: boolean }>) {
  // La carte à jour après le clic, avant que la conversation ne la recharge.
  const [decidee, setDecidee] = useState<CarteEcriture | null>(null);
  const decider = useDeciderEcritureMutation(conversationId);
  const affichee = decidee ?? carte;
  const proposee = affichee.statut === "proposee";
  const reussie = affichee.statut === "confirmee";

  function cliquer(decision: "confirmer" | "annuler") {
    decider.mutate({ id: affichee.id, decision }, { onSuccess: setDecidee });
  }

  const erreur = messageErreur(decider.error, "La décision n'a pas pu être envoyée. Réessayez.");

  return (
    <section
      aria-label="Carte de confirmation Moduléo"
      className="flex max-w-[70%] flex-col gap-2 self-start rounded-md border bg-background px-3 py-2 text-sm"
    >
      <p className="font-medium">Écriture dans Moduléo : {affichee.titre}</p>
      {affichee.rubrique && <p className="font-medium text-destructive">{affichee.rubrique}</p>}
      {affichee.fiche && <p className="whitespace-pre-line break-words">{affichee.fiche}</p>}
      {affichee.lignes.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
          {affichee.lignes.map((ligne) => (
            <div key={ligne.champ} className="contents">
              <dt className="text-muted-foreground">{ligne.champ}</dt>
              <dd className="break-words">
                {ligne.avant == null ? (
                  ligne.valeur
                ) : (
                  <>
                    <span className="text-muted-foreground line-through">{ligne.avant}</span> → {ligne.valeur}
                  </>
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {proposee ? (
        <div className="flex items-center gap-2">
          <Button size="sm" disabled={desactivee || decider.isPending} onClick={() => cliquer("confirmer")}>
            {decider.isPending && <Loader2 className="animate-spin" aria-hidden="true" />}
            Confirmer
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={desactivee || decider.isPending}
            onClick={() => cliquer("annuler")}
          >
            Annuler
          </Button>
        </div>
      ) : (
        <output className={cn("text-sm", reussie ? "text-primary" : "text-muted-foreground")}>
          {affichee.message}
        </output>
      )}
      {erreur && (
        <p role="alert" className="text-sm text-destructive">
          {erreur}
        </p>
      )}
    </section>
  );
}
