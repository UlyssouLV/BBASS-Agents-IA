import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import ChangelogListe from '../components/ChangelogListe';
import FeuilleDeRouteAccueil from '../components/FeuilleDeRouteAccueil';
import styles from './accueil.module.css';

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout title="Documentation" description={siteConfig.tagline}>
      <main className={`container margin-vert--xl ${styles.page}`}>
        <div className={styles.colonnes}>
          <div className={styles.colonneGauche}>
            <Heading as="h1">{siteConfig.title}</Heading>
            <p>{siteConfig.tagline}</p>
            <p className={styles.actions}>
              <Link className="button button--primary button--lg" to="/docs/features/">
                Features
              </Link>
              <Link className="button button--secondary button--lg" to="/docs/glossaire">
                Glossaire
              </Link>
            </p>

            <Heading as="h2" className={styles.sousTitre}>
              Dernières versions
            </Heading>
            <ChangelogListe limite={5} />
            <p className="margin-top--md">
              <Link to="/docs/changelog/">Tout le changelog →</Link>
            </p>
          </div>

          <aside className={styles.colonneDroite}>
            <Heading as="h2">Feuille de route</Heading>
            <p className={styles.intro}>Prochaines versions prévues.</p>
            <FeuilleDeRouteAccueil />
          </aside>
        </div>
      </main>
    </Layout>
  );
}
