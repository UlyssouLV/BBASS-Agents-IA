import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import clsx from 'clsx';

import changelog from '../data/changelog.json';
import styles from './changelog.module.css';

export type EntreeChangelog = {
  version: string;
  serie?: string;
  date: string;
  dateIso?: string;
  titre: string;
  href: string;
};

type Props = {
  /** Nombre max d’entrées (accueil). Absent = toutes. */
  limite?: number;
  /** Affiche des en-têtes de série (1.4, 1.3, …) — sommaire Changelog. */
  groupes?: boolean;
  className?: string;
};

const entrees = changelog as EntreeChangelog[];

function serieDe(entree: EntreeChangelog): string {
  if (entree.serie) {
    return entree.serie;
  }
  const v = entree.version.replace(/^v/i, '');
  const parts = v.split('.');
  return parts.length >= 2 ? `${parts[0]}.${parts[1]}` : v;
}

function grouperParSerie(liste: EntreeChangelog[]): {serie: string; items: EntreeChangelog[]}[] {
  const ordre: string[] = [];
  const map = new Map<string, EntreeChangelog[]>();
  for (const entree of liste) {
    const serie = serieDe(entree);
    if (!map.has(serie)) {
      ordre.push(serie);
      map.set(serie, []);
    }
    map.get(serie)!.push(entree);
  }
  return ordre.map((serie) => ({serie, items: map.get(serie)!}));
}

function LigneVersion({
  entree,
  pointActuel,
}: {
  entree: EntreeChangelog;
  pointActuel: boolean;
}): ReactNode {
  return (
    <li className={styles.etape}>
      <Link className={styles.carte} to={entree.href}>
        <span className={styles.rail} aria-hidden="true">
          <span className={clsx(styles.point, pointActuel && styles.pointActuel)} />
        </span>
        <span className={styles.corps}>
          <span className={styles.meta}>
            <span className={styles.version}>{entree.version}</span>
            <time className={styles.date} dateTime={entree.dateIso || undefined}>
              {entree.date}
            </time>
          </span>
          <span className={styles.titre}>{entree.titre}</span>
        </span>
        <span className={styles.fleche} aria-hidden="true">
          →
        </span>
      </Link>
    </li>
  );
}

export default function ChangelogListe({
  limite,
  groupes = false,
  className,
}: Props): ReactNode {
  const visibles =
    typeof limite === 'number' ? entrees.slice(0, limite) : entrees;

  if (visibles.length === 0) {
    return (
      <p className={styles.vide}>
        Aucune release chargée — lance <code>npm run generer-changelog</code>.
      </p>
    );
  }

  if (!groupes) {
    return (
      <ol className={clsx(styles.fil, className)}>
        {visibles.map((entree, index) => (
          <LigneVersion
            key={entree.version}
            entree={entree}
            pointActuel={index === 0}
          />
        ))}
      </ol>
    );
  }

  const groupesSerie = grouperParSerie(visibles);

  return (
    <div className={clsx(styles.groupes, className)}>
      {groupesSerie.map((groupe, gIndex) => (
        <section key={groupe.serie} className={styles.groupe}>
          <h2 className={styles.groupeTitre}>
            <span className={styles.groupeBadge}>{groupe.serie}</span>
            <span className={styles.groupeMeta}>
              {groupe.items.length} version{groupe.items.length > 1 ? 's' : ''}
            </span>
          </h2>
          <ol className={styles.fil}>
            {groupe.items.map((entree, index) => (
              <LigneVersion
                key={entree.version}
                entree={entree}
                pointActuel={gIndex === 0 && index === 0}
              />
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}
