import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout title="Documentation" description={siteConfig.tagline}>
      <main className="container margin-vert--xl">
        <Heading as="h1">{siteConfig.title}</Heading>
        <p>{siteConfig.tagline}</p>
        <p style={{display: 'flex', gap: '0.75rem', flexWrap: 'wrap'}}>
          <Link className="button button--primary button--lg" to="/docs/features/inspecteur/">
            Inspecteur des échanges
          </Link>
          <Link className="button button--secondary button--lg" to="/docs/glossaire">
            Glossaire
          </Link>
        </p>
      </main>
    </Layout>
  );
}
