import type {ReactNode} from 'react';

import styles from './sectionDoc.module.css';

type Variante = 'fonctionnelle' | 'technique';

type Props = {
  variante: Variante;
  /** Remplace le sous-titre par défaut (ex. chemin de la spec). */
  sousTitre?: string;
  children: ReactNode;
};

function IconeProduit(): ReactNode {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M1.5 2.75A.75.75 0 0 1 2.25 2h11.5a.75.75 0 0 1 0 1.5H2.25a.75.75 0 0 1-.75-.75Zm0 5A.75.75 0 0 1 2.25 7h7.5a.75.75 0 0 1 0 1.5h-7.5A.75.75 0 0 1 1.5 7.75Zm0 5a.75.75 0 0 1 .75-.75h11.5a.75.75 0 0 1 0 1.5H2.25a.75.75 0 0 1-.75-.75Z"
      />
    </svg>
  );
}

function IconeTechnique(): ReactNode {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="m11.28 3.22 1.5 1.5a.75.75 0 0 1 0 1.06l-6.75 6.75a.75.75 0 0 1-.34.19l-3 .75a.75.75 0 0 1-.91-.91l.75-3a.75.75 0 0 1 .19-.34l6.75-6.75a.75.75 0 0 1 1.06 0Zm.22.78L5.06 10.44l-.4 1.6 1.6-.4L12.5 5l-.5-.5-.5-.5Z"
      />
    </svg>
  );
}

const META: Record<
  Variante,
  {titre: string; sousTitre: string; icone: () => ReactNode; classe: string}
> = {
  fonctionnelle: {
    titre: 'Documentation fonctionnelle',
    sousTitre: 'Ce que change la version pour les collaborateurs',
    icone: IconeProduit,
    classe: styles.fonctionnelle,
  },
  technique: {
    titre: 'Documentation technique',
    sousTitre: 'Spec versionnée dans le dépôt',
    icone: IconeTechnique,
    classe: styles.technique,
  },
};

export default function SectionDoc({
  variante,
  sousTitre,
  children,
}: Props): ReactNode {
  const meta = META[variante];
  const Icone = meta.icone;
  const id =
    variante === 'fonctionnelle'
      ? 'documentation-fonctionnelle'
      : 'documentation-technique';
  return (
    <section className={`${styles.encadre} ${meta.classe}`}>
      <header className={styles.bandeau}>
        <span className={styles.icone}>
          <Icone />
        </span>
        <div>
          <h2 className={styles.titre} id={id}>
            {meta.titre}
          </h2>
          <p className={styles.sousTitre}>{sousTitre ?? meta.sousTitre}</p>
        </div>
      </header>
      <div className={styles.corps}>{children}</div>
    </section>
  );
}
