import * as React from "react";

import { cn } from "@/lib/utils";

// Structure minimale (pas de collapse, pas de variante mobile) : la
// disposition « façon ChatGPT » (issue #74) n'exige qu'une colonne
// permanente à gauche de l'écran Compte, jamais repliée ni utilisée hors
// desktop pour l'instant (voir docs/specs/v1.2.1-identite-visuelle-disposition.md,
// Out of Scope).
function Sidebar({ className, ...props }: React.ComponentProps<"aside">) {
  return (
    <aside
      data-slot="sidebar"
      className={cn("flex h-screen w-64 shrink-0 flex-col border-r border-border bg-card", className)}
      {...props}
    />
  );
}

function SidebarHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="sidebar-header" className={cn("flex flex-col gap-2 p-4", className)} {...props} />;
}

function SidebarContent({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="sidebar-content" className={cn("flex-1 overflow-y-auto px-4 pb-4", className)} {...props} />
  );
}

function SidebarFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div data-slot="sidebar-footer" className={cn("flex flex-col gap-2 border-t border-border p-4", className)} {...props} />
  );
}

export { Sidebar, SidebarHeader, SidebarContent, SidebarFooter };
