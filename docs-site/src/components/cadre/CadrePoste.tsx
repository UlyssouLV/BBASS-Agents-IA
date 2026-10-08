import { useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

import cssPoste from '@site/src/poste/cadreCss.js';

import styles from './cadre.module.css';

let feuille: CSSStyleSheet | null = null;

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
      {montage ? createPortal(children, montage) : null}
    </div>
  );
}
