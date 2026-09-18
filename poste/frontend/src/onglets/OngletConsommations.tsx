import { useComptesConsommationQuery, type CompteConsommation } from "@/hooks/useComptes";
import type { DetailConsommationCategorie } from "@/hooks/useConsommation";
import { ErreurApi } from "@/lib/api";

function formaterDetail(detail: DetailConsommationCategorie): string {
  const parties = [`${detail.nombre_requetes} requête(s)`];
  if (detail.tokens_total) {
    parties.push(`${detail.tokens_total} tokens`);
  }
  if (detail.pages_traitees) {
    parties.push(`${detail.pages_traitees} page(s)`);
  }
  parties.push(`${detail.cout_usd} $`);
  return parties.join(" · ");
}

// Réécriture React de la future section #onglet-consommations d'app.js :
// liste des comptes classée par coût décroissant (déjà triée côté VM
// centrale, voir vm_centrale.routers.comptes.lister_consommation_comptes),
// chacun avec son détail Chat / Pièce jointe agrégé. Jamais de détail par
// conversation individuelle (confidentialité, inchangé depuis 1.1.3) — voir
// docs/specs/v1.2.0-interface-poste.md et issue #66.
export function OngletConsommations() {
  const consommationComptesQuery = useComptesConsommationQuery();

  if (consommationComptesQuery.isLoading) {
    return <output>Chargement…</output>;
  }

  if (consommationComptesQuery.error) {
    const message =
      consommationComptesQuery.error instanceof ErreurApi
        ? consommationComptesQuery.error.message
        : "Le chargement de la consommation des comptes a échoué. Réessayez plus tard.";
    return (
      <p role="alert" className="text-sm text-destructive">
        {message}
      </p>
    );
  }

  const comptes: CompteConsommation[] = consommationComptesQuery.data ?? [];

  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold">Consommations</h2>
      {comptes.length === 0 ? (
        <p className="text-sm text-muted-foreground">Aucune consommation enregistrée.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="py-1.5 pr-4 font-medium">Compte</th>
              <th className="py-1.5 pr-4 font-medium">Coût total</th>
              <th className="py-1.5 pr-4 font-medium">Chat</th>
              <th className="py-1.5 font-medium">Pièce jointe</th>
            </tr>
          </thead>
          <tbody>
            {comptes.map((compte) => (
              <tr key={compte.identifiant} className="border-b border-border last:border-0">
                <td className="py-1.5 pr-4">
                  {compte.prenom} {compte.nom} ({compte.identifiant})
                </td>
                <td className="py-1.5 pr-4">{compte.cout_usd} $</td>
                <td className="py-1.5 pr-4">{formaterDetail(compte.chat)}</td>
                <td className="py-1.5">{formaterDetail(compte.piece_jointe)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
