import { useEtatServeurBbass } from "@/hooks/useConfiguration";
import { cn } from "@/lib/utils";

// État du Serveur BBASS lu sur /sante (spec 1.6.2, point 9) : vert avec sa
// version, orange tant qu'il ne répond pas (nouvel essai toutes les 5 s).
export function PastilleServeurBbass({ className }: Readonly<{ className?: string }>) {
  const { data, isPending } = useEtatServeurBbass();

  if (isPending) {
    return null;
  }

  const joignable = data?.joignable === true;
  return (
    <p
      role="status"
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium",
        joignable
          ? "border-emerald-600/25 bg-emerald-50 text-emerald-800"
          : "border-amber-600/30 bg-amber-50 text-amber-900",
        className
      )}
    >
      <span
        aria-hidden="true"
        className={cn("size-2 rounded-full", joignable ? "bg-emerald-600" : "animate-pulse bg-amber-500")}
      />
      {joignable ? `Connecté à BBASS v${data?.version}` : "Serveur BBASS injoignable, nouvel essai…"}
    </p>
  );
}
