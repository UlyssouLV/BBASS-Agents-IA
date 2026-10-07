import {useState, type ReactNode} from 'react';

import styles from './apercus.module.css';

export interface CarteApercuProps {
  libelle: string;
  origine: 'mistral' | 'local';
  statut?: 'succes' | 'echec';
  date?: string;
  modele?: string;
  /** Carte déjà dépliée à l’affichage (ex. exemple principal d’une fiche). */
  ouvertParDefaut?: boolean;
  children?: ReactNode;
}

// En-tête identique à CarteEchangeInspecteur : libellé, badge d’origine,
// badge de statut, date. Le dépliage montre l’explication passée en children.
export default function CarteApercu({
  libelle,
  origine,
  statut = 'succes',
  date = '6 oct. 2026, 14:02',
  modele,
  ouvertParDefaut = false,
  children,
}: CarteApercuProps): ReactNode {
  const [ouvert, setOuvert] = useState(ouvertParDefaut);
  const local = origine === 'local';
  const enEchec = statut === 'echec';

  return (
    <article className={styles.carte}>
      <button
        type="button"
        className={styles.barre}
        aria-expanded={ouvert}
        onClick={() => setOuvert((valeur) => !valeur)}>
        <span className={styles.chevron} aria-hidden="true">
          {ouvert ? '▼' : '▶'}
        </span>
        <span className={styles.libelle}>{libelle}</span>
        <span className={styles.badge}>{local ? 'Local' : 'Mistral'}</span>
        <span className={enEchec ? styles.badgeKo : styles.badgeOk}>
          {enEchec ? 'Échec' : 'Succès'}
        </span>
        <time className={styles.date}>{date}</time>
      </button>
      {ouvert && (
        <div className={styles.detail}>
          {!local && modele && <p className={styles.modele}>Modèle : {modele}</p>}
          {children}
        </div>
      )}
    </article>
  );
}

export function SectionApercu({
  titre,
  children,
}: {
  titre: string;
  children: ReactNode;
}): ReactNode {
  return (
    <section className={styles.section}>
      <h4>{titre}</h4>
      {children}
    </section>
  );
}

export function MessageApercu({role, children}: {role: string; children: ReactNode}): ReactNode {
  return (
    <div className={styles.message}>
      <span className={styles.role}>{role}</span>
      <div>{children}</div>
    </div>
  );
}

export function JsonApercu({children}: {children: string}): ReactNode {
  return <pre className={styles.pre}>{children}</pre>;
}
