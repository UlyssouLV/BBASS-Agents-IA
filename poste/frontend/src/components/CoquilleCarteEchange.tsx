import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";

interface CoquilleCarteEchangeProps {
  libelle: string;
  local: boolean;
  enEchec: boolean;
  dateIso: string;
  ouvert?: boolean;
  onOuvertChange?: (ouvert: boolean) => void;
  ouvertParDefaut?: boolean;
  children?: ReactNode;
}

// En-tête de carte d'échange : libellé, origine, statut, date. Le corps
// (payload réel ou exemple de la doc) est passé en children.
export function CoquilleCarteEchange({
  libelle,
  local,
  enEchec,
  dateIso,
  ouvert,
  onOuvertChange,
  ouvertParDefaut = false,
  children,
}: Readonly<CoquilleCarteEchangeProps>) {
  const [interne, setInterne] = useState(ouvertParDefaut);
  const deplie = ouvert ?? interne;
  const Chevron = deplie ? ChevronDown : ChevronRight;

  function basculer() {
    const suivant = !deplie;
    onOuvertChange?.(suivant);
    if (ouvert === undefined) {
      setInterne(suivant);
    }
  }

  return (
    <article className="rounded-md border bg-card text-sm">
      <button
        type="button"
        aria-expanded={deplie}
        onClick={basculer}
        className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-muted/50"
      >
        <Chevron className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="font-medium">{libelle}</span>
        <Badge variant="outline">{local ? "Local" : "Mistral"}</Badge>
        <Badge variant={enEchec ? "destructive" : "secondary"}>{enEchec ? "Échec" : "Succès"}</Badge>
        <span className="ml-auto text-xs text-muted-foreground">
          <time dateTime={dateIso}>{new Date(dateIso).toLocaleString()}</time>
        </span>
      </button>
      {deplie && <div className="flex flex-col gap-3 border-t px-3 py-3">{children}</div>}
    </article>
  );
}

export function SectionEchange({ titre, children }: Readonly<{ titre: string; children: ReactNode }>) {
  return (
    <section className="flex flex-col gap-1.5">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{titre}</h3>
      {children}
    </section>
  );
}

export function BlocTexte({ children, className }: Readonly<{ children: ReactNode; className?: string }>) {
  return (
    <pre
      className={`max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md bg-muted px-3 py-2 font-mono text-xs ${className ?? ""}`}
    >
      {children}
    </pre>
  );
}

export function MessageRole({ role, children }: Readonly<{ role: string; children: ReactNode }>) {
  return (
    <div className="flex flex-col gap-1 rounded-md border px-3 py-2">
      <span className="text-xs font-semibold">{role}</span>
      {children}
    </div>
  );
}
