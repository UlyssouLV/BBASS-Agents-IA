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

interface PartCout {
  pourcentage: number;
  debut: number;
  trait: string;
  pastille: string;
}

// Répartition du coût total entre chat et pièce jointe (issue #88), ou null
// quand il n'y a encore rien à répartir. Le complément à 100 plutôt qu'un
// second arrondi : les deux parts font toujours un camembert entier, et le
// tracé comme le tableau lisent le même chiffre.
function repartitionCout(coutChat: number, coutPieceJointe: number): [PartCout, PartCout] | null {
  const total = coutChat + coutPieceJointe;
  if (!Number.isFinite(total) || total <= 0) {
    return null;
  }

  const pourcentageChat = Math.round((coutChat / total) * 100);
  return [
    { pourcentage: pourcentageChat, debut: 0, trait: "stroke-primary", pastille: "bg-primary" },
    { pourcentage: 100 - pourcentageChat, debut: pourcentageChat, trait: "stroke-accent", pastille: "bg-accent" },
  ];
}

// Camembert à deux parts : pas de bibliothèque de graphiques, un cercle dont
// le trait (rayon 25, épaisseur 50) remplit le disque, avec pathLength=100
// pour exprimer les tirets directement en pourcentage. Les pastilles de
// couleur du tableau voisin servent de légende.
function CamembertRepartitionCout({ parts, description }: Readonly<{ parts: PartCout[]; description: string }>) {
  return (
    <svg viewBox="0 0 100 100" role="img" aria-label={`Répartition du coût total : ${description}`} className="size-32 shrink-0 -rotate-90">
      {parts.map((part) => (
        <circle
          key={part.trait}
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
  const parts = repartitionCout(Number(consommation.chat.cout_usd), Number(consommation.piece_jointe.cout_usd));
  const categories = [
    { libelle: "Chat", detail: consommation.chat, part: parts?.[0] },
    { libelle: "Pièce jointe", detail: consommation.piece_jointe, part: parts?.[1] },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="mb-2 text-sm font-semibold">Total</h2>
        <div className="flex items-center gap-6">
          {parts ? (
            <CamembertRepartitionCout
              parts={parts}
              description={parts.map((part, index) => `${categories[index].libelle} ${part.pourcentage} %`).join(", ")}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              Aucune consommation enregistrée pour l'instant : pas de répartition à afficher.
            </p>
          )}

          <table className="w-full text-sm">
            <tbody>
              {categories.map((categorie) => (
                <tr key={categorie.libelle} className="border-b border-border last:border-0">
                  <th scope="row" className="py-1.5 pr-4 text-left font-medium">
                    <span className="flex items-center gap-2">
                      {categorie.part ? (
                        <span aria-hidden="true" className={`size-3 shrink-0 rounded-full ${categorie.part.pastille}`} />
                      ) : null}
                      {categorie.libelle}
                    </span>
                  </th>
                  <td className="py-1.5">{formaterDetail(categorie.detail)}</td>
                  {categorie.part ? <td className="py-1.5 pl-4 text-right">{categorie.part.pourcentage} %</td> : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
