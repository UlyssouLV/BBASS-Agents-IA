import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import clsx from 'clsx';

import bugsData from '../data/bugs.json';
import styles from './bugsConnus.module.css';

type BugAccueil = {
  issue: number;
  titre: string;
  href: string;
  complet: boolean;
  manques: string[];
  resume: string;
  priorite: string;
};

type Donnees = {
  bugs: BugAccueil[];
};

const donnees = bugsData as Donnees;

export default function BugsConnusAccueil(): ReactNode {
  if (donnees.bugs.length === 0) {
    return <p className={styles.vide}>Aucun bug connu pour le moment.</p>;
  }

  return (
    <ol className={styles.fil}>
      {donnees.bugs.map((bug) => (
        <li key={bug.issue} className={styles.etape}>
          <Link className={styles.carte} to={bug.href}>
            <span className={styles.rail} aria-hidden="true">
              <span
                className={clsx(
                  styles.point,
                  !bug.complet && styles.pointIncomplet,
                )}
              />
            </span>
            <span className={styles.corps}>
              <span className={styles.meta}>
                <span className={styles.issue}>#{bug.issue}</span>
                {bug.priorite &&
                bug.priorite !== 'Informations manquantes' ? (
                  <span className={styles.priorite}>{bug.priorite}</span>
                ) : null}
              </span>
              <span className={styles.titre}>{bug.titre}</span>
              {bug.resume ? (
                <span className={styles.resume}>{bug.resume}</span>
              ) : null}
              {!bug.complet && bug.manques.length > 0 ? (
                <span className={styles.manques}>
                  Infos manquantes : {bug.manques.join(' · ')}
                </span>
              ) : null}
            </span>
            <span className={styles.fleche} aria-hidden="true">
              →
            </span>
          </Link>
        </li>
      ))}
    </ol>
  );
}
