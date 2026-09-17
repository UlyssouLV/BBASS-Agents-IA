import {
  conversationsParCoutDecroissant,
  useConsommationQuery,
  type DetailConsommationCategorie,
} from "@/hooks/useConsommation";
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

// Réécriture React de la section #onglet-consommation d'app.js : total
// global (chat vs pièce jointe) puis classement des conversations par coût
// décroissant, lecture seule (voir docs/specs/v1.2.0-interface-poste.md et
// issue #64).
export function OngletConsommation() {
  const consommationQuery = useConsommationQuery();

  if (consommationQuery.isLoading) {
    return <p role="status">Chargement…</p>;
  }

  if (consommationQuery.error) {
    const message =
      consommationQuery.error instanceof ErreurApi
        ? consommationQuery.error.message
        : "Le chargement de la consommation a échoué. Réessayez plus tard.";
    return (
      <p role="alert" className="text-sm text-destructive">
        {message}
      </p>
    );
  }

  const consommation = consommationQuery.data;
  if (!consommation) {
    return null;
  }

  const conversations = conversationsParCoutDecroissant(consommation.conversations);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h3 className="mb-2 text-sm font-semibold">Total</h3>
        <table className="w-full text-sm">
          <tbody>
            <tr className="border-b border-border">
              <td className="py-1.5 pr-4 font-medium">Chat</td>
              <td className="py-1.5">{formaterDetail(consommation.chat)}</td>
            </tr>
            <tr>
              <td className="py-1.5 pr-4 font-medium">Pièce jointe</td>
              <td className="py-1.5">{formaterDetail(consommation.piece_jointe)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold">Conversations</h3>
        {conversations.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune conversation avec de la consommation enregistrée.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="py-1.5 pr-4 font-medium">Conversation</th>
                <th className="py-1.5 pr-4 font-medium">Coût total</th>
                <th className="py-1.5 pr-4 font-medium">Chat</th>
                <th className="py-1.5 font-medium">Pièce jointe</th>
              </tr>
            </thead>
            <tbody>
              {conversations.map((conversation) => (
                <tr key={conversation.id} className="border-b border-border last:border-0">
                  <td className="truncate py-1.5 pr-4">{conversation.titre}</td>
                  <td className="py-1.5 pr-4">{conversation.cout_usd} $</td>
                  <td className="py-1.5 pr-4">{formaterDetail(conversation.chat)}</td>
                  <td className="py-1.5">{formaterDetail(conversation.piece_jointe)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
