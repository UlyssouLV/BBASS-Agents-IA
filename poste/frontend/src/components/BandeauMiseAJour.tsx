import { useState } from "react";
import { TriangleAlert, X } from "lucide-react";

import { useMiseAJour } from "@/hooks/useMiseAJour";

// Mise à jour au lancement en échec (spec 1.6.2, point 5) : le texte vient du
// Lanceur. Par-dessus l'écran, sur toute la largeur, jusqu'à ce qu'on le ferme.
export function BandeauMiseAJour() {
  const { data } = useMiseAJour();
  const [ferme, setFerme] = useState(false);

  if (!data?.bandeau || ferme) {
    return null;
  }

  return (
    <div
      role="alert"
      className="fixed inset-x-0 top-0 z-50 flex items-center gap-3 border-b border-accent/30 bg-accent px-4 py-2 text-sm text-accent-foreground shadow-sm"
    >
      <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
      <p className="flex-1">{data.bandeau}</p>
      <button
        type="button"
        onClick={() => setFerme(true)}
        aria-label="Fermer le bandeau"
        className="rounded p-1 hover:bg-accent-foreground/15 focus-visible:outline-2 focus-visible:outline-accent-foreground"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </div>
  );
}
