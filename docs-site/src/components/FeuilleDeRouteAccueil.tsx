import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import clsx from 'clsx';

import feuille from '../data/feuille-de-route.json';
import styles from './feuilleDeRoute.module.css';

type Version = {
  version: string;
  titre: string;
  resume: string;
  href: string;
};

type Donnees = {
  versions: Version[];
  plusTard: string[];
};

const donnees = feuille as Donnees;

export default function FeuilleDeRouteAccueil(): ReactNode {
  if (donnees.versions.length === 0) {
    return (
      <p className={styles.vide}>
        Feuille de route indisponible — lance{' '}
        <code>npm run generer-feuille-de-route</code>.
      </p>
    );
  }

  return (
    <div className={styles.bloc}>
      <ol className={styles.liste}>
        {donnees.versions.map((v, index) => (
          <li key={v.version}>
            <Link
              className={clsx(styles.carte, index === 0 && styles.carteProchaine)}
              to={v.href}>
              <div className={styles.bandeau}>
                <span className={styles.badge}>{v.version}</span>
                {index === 0 && <span className={styles.prochaine}>Prochaine</span>}
              </div>
              <h3 className={styles.titre}>{v.titre}</h3>
              {v.resume ? <p className={styles.resume}>{v.resume}</p> : null}
              <span className={styles.lire}>Lire la proposition →</span>
            </Link>
          </li>
        ))}
      </ol>
      {donnees.plusTard.length > 0 ? (
        <div className={styles.plusTard}>
          <p className={styles.plusTardTitre}>Plus tard</p>
          <ul className={styles.chips}>
            {donnees.plusTard.map((sujet) => (
              <li key={sujet} className={styles.chip}>
                {sujet}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
