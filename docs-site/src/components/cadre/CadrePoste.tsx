import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import cssPoste from '@site/src/poste/cadreCss.js';

import styles from './cadre.module.css';

let feuille: CSSStyleSheet | null = null;

// Certains composants du poste (menu « … ») appellent leurs hooks de
// requête : sur le site de doc il n'y a pas de backend, rien ne part.
const clientRequetes = new QueryClient({
  defaultOptions: {queries: {enabled: false, retry: false}},
});

function feuillePoste(): CSSStyleSheet {
  if (!feuille) {
    feuille = new CSSStyleSheet();
    feuille.replaceSync(cssPoste);
  }
  return feuille;
}

// Les styles du poste vivent dans ce shadow root. Ils ne s'appliquent pas
// au menu ni au texte du site de doc.
export default function CadrePoste({
  children,
  etroit = false,
}: {
  children: ReactNode;
  etroit?: boolean;
}): ReactNode {
  const hote = useRef<HTMLDivElement>(null);
  const [montage, setMontage] = useState<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    const element = hote.current;
    if (!element) {
      return;
    }
    const shadow = element.shadowRoot ?? element.attachShadow({ mode: 'open' });
    shadow.adoptedStyleSheets = [feuillePoste()];
    let cible = shadow.querySelector<HTMLDivElement>('[data-montage]');
    if (!cible) {
      cible = document.createElement('div');
      cible.dataset.montage = '';
      shadow.appendChild(cible);
    }
    setMontage(cible);
  }, []);

  return (
    <div ref={hote} className={etroit ? styles.etroit : styles.cadre}>
      {montage
        ? createPortal(
            <QueryClientProvider client={clientRequetes}>{children}</QueryClientProvider>,
            montage,
          )
        : null}
    </div>
  );
}
