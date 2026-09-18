import type { CSSProperties } from "react";
import { Toaster as Sonner, type ToasterProps } from "sonner";

// Pas de thème sombre dans ce front (voir src/index.css, un seul :root) :
// contrairement au composant shadcn/ui par défaut, pas de next-themes ici.
function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="light"
      className="toaster group"
      style={
        {
          "--normal-bg": "var(--background)",
          "--normal-text": "var(--foreground)",
          "--normal-border": "var(--border)",
        } as CSSProperties
      }
      {...props}
    />
  );
}

export { Toaster };
