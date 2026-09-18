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

// Camembert de répartition du coût total entre chat et pièce jointe (issue
// #88), en complément du tableau « Total » qui garde les valeurs exactes.
// Deux parts seulement : pas de bibliothèque de graphiques, un cercle dont le
// trait (rayon 25, épaisseur 50) remplit le disque, avec pathLength=100 pour
// exprimer les tirets directement en pourcentage.
function CamembertRepartitionCout({ coutChat, coutPieceJointe }: Readonly<{ coutChat: number; coutPieceJointe: number }>) {
  const total = coutChat + coutPieceJointe;

  if (!Number.isFinite(total) || total <= 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucune consommation enregistrée pour l'instant : pas de répartition à afficher.
      </p>
    );
  }

  // Le complément à 100 plutôt qu'un second arrondi : les deux parts font
  // toujours un camembert entier, affichage et tracé sur le même chiffre.
  const pourcentageChat = Math.round((coutChat / total) * 100);
  const parts = [
    { libelle: "Chat", pourcentage: pourcentageChat, debut: 0, trait: "stroke-primary", pastille: "bg-primary" },
    {
      libelle: "Pièce jointe",
      pourcentage: 100 - pourcentageChat,
      debut: pourcentageChat,
      trait: "stroke-accent",
      pastille: "bg-accent",
    },
  ];
  const description = parts.map((part) => `${part.libelle} ${part.pourcentage} %`).join(", ");

  return (
    <div className="flex items-center gap-6">
      <svg viewBox="0 0 100 100" role="img" aria-label={`Répartition du coût total : ${description}`} className="size-32 -rotate-90">
        {parts.map((part) => (
          <circle
            key={part.libelle}
            cx="50"
            cy="50"
            r="25"
            fill="none"
            strokeWidth="50"
            pathLength={100}
            strokeDasharray={`${part.pourcentage} 100`}
            strokeDashoffset={-part.debut}
            className={part.trait}
          />
        ))}
      </svg>
      <ul className="flex flex-col gap-2 text-sm">
        {parts.map((part) => (
          <li key={part.libelle} className="flex items-center gap-2">
            <span aria-hidden="true" className={`size-3 shrink-0 rounded-full ${part.pastille}`} />
            <span>
              {part.libelle} — {part.pourcentage} %
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// Réécriture React de la section #onglet-consommation d'app.js : total
// global (chat vs pièce jointe) puis classement des conversations par coût
// décroissant, lecture seule (voir docs/specs/v1.2.0-interface-poste.md et
// issue #64).
export function OngletConsommation() {
  const consommationQuery = useConsommationQuery();

  if (consommationQuery.isLoading) {
    return <output>Chargement…</output>;
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
        <h2 className="mb-2 text-sm font-semibold">Total</h2>
        <table className="w-full text-sm">
          <tbody>
            <tr className="border-b border-border">
              <th scope="row" className="py-1.5 pr-4 text-left font-medium">
                Chat
              </th>
              <td className="py-1.5">{formaterDetail(consommation.chat)}</td>
            </tr>
            <tr>
              <th scope="row" className="py-1.5 pr-4 text-left font-medium">
                Pièce jointe
              </th>
              <td className="py-1.5">{formaterDetail(consommation.piece_jointe)}</td>
            </tr>
          </tbody>
        </table>

        <h3 className="mt-4 mb-2 text-sm font-medium">Répartition du coût</h3>
        <CamembertRepartitionCout
          coutChat={Number(consommation.chat.cout_usd)}
          coutPieceJointe={Number(consommation.piece_jointe.cout_usd)}
        />
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold">Conversations</h2>
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
