import * as React from "react";

import { cn } from "@/lib/utils";

// Champ de saisie du message (issue #76) : plus grand et plus arrondi qu'un
// Input shadcn (`h-9` / `rounded-md`), réutilisé à l'identique pour une
// nouvelle conversation et une conversation ouverte.
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-24 w-full min-w-0 resize-none rounded-2xl border border-input bg-transparent px-4 py-3 text-sm shadow-xs transition-colors outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}

export { Textarea };
