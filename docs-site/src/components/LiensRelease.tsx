import type {ReactNode} from 'react';

import styles from './liensRelease.module.css';

export type LienTicket = {
  number: string;
  href: string;
};

type Props = {
  releaseUrl: string;
  releaseLabel?: string;
  prUrl?: string | null;
  prLabel?: string | null;
  specUrl?: string | null;
  specLabel?: string | null;
  tickets?: LienTicket[];
};

function IconeGithub(): ReactNode {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.6 7.6 0 0 1 8 3.58c.68 0 1.36.09 2 .26 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z"
      />
    </svg>
  );
}

function IconePr(): ReactNode {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M7.177 3.073 9.573.677A.25.25 0 0 1 10 .854v4.792a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm-2.25.75a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25ZM11 2.5h-1V4h1a1 1 0 0 1 1 1v5.628a2.251 2.251 0 1 0 1.5 0V5A2.5 2.5 0 0 0 11 2.5Zm1.75 9.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM3.75 12a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Z"
      />
    </svg>
  );
}

function IconeSpec(): ReactNode {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M3.75 1.5a.25.25 0 0 0-.25.25v11.5c0 .138.112.25.25.25h8.5a.25.25 0 0 0 .25-.25V6H9.75A.75.75 0 0 1 9 5.25V1.5Zm6.75.56v2.69h2.69ZM2 1.75C2 .784 2.784 0 3.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v8.586A1.75 1.75 0 0 1 12.25 15h-8.5A1.75 1.75 0 0 1 2 13.25Zm2.75 5.5a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1-.75-.75Zm0 3a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1-.75-.75Z"
      />
    </svg>
  );
}

function IconeTickets(): ReactNode {
  return (
    <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path
        fill="currentColor"
        d="M2.5 1.75v11.5c0 .138.112.25.25.25h3.17a.75.75 0 0 1 0 1.5H2.75A1.75 1.75 0 0 1 1 13.25V1.75C1 .784 1.784 0 2.75 0h8.5C12.216 0 13 .784 13 1.75v5.5a.75.75 0 0 1-1.5 0V1.75a.25.25 0 0 0-.25-.25h-8.5a.25.25 0 0 0-.25.25Zm9.19 9.5.72-.72a.75.75 0 1 1 1.06 1.06l-1.25 1.25a.75.75 0 0 1-1.06 0l-.75-.75a.75.75 0 1 1 1.06-1.06l.22.22ZM4.75 4a.75.75 0 0 0 0 1.5h4.5a.75.75 0 0 0 0-1.5Zm0 3a.75.75 0 0 0 0 1.5h2a.75.75 0 0 0 0-1.5Z"
      />
    </svg>
  );
}

function numeroDepuisUrl(url: string | null | undefined): string | null {
  if (!url) {
    return null;
  }
  const m = url.match(/\/(?:pull|issues)\/(\d+)/);
  return m ? `#${m[1]}` : null;
}

export default function LiensRelease({
  releaseUrl,
  releaseLabel = 'Sur GitHub',
  prUrl,
  prLabel,
  specUrl,
  specLabel,
  tickets = [],
}: Props): ReactNode {
  const prTitre = prLabel || numeroDepuisUrl(prUrl) || 'Ouvrir';
  const specTitre = specLabel || 'Spec versionnée';
  const [parent, ...enfants] = tickets;

  return (
    <nav className={styles.bandeau} aria-label="Liens de la version">
      <div className={styles.cartes}>
        <a
          className={styles.carte}
          href={releaseUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          <span className={styles.icone}>
            <IconeGithub />
          </span>
          <span className={styles.corps}>
            <span className={styles.eyebrow}>
              Release
              <span className={styles.fleche} aria-hidden="true">
                →
              </span>
            </span>
            <span className={styles.titre}>GitHub Release</span>
            <span className={styles.sousTitre}>{releaseLabel}</span>
          </span>
        </a>

        {prUrl ? (
          <a
            className={styles.carte}
            href={prUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className={styles.icone}>
              <IconePr />
            </span>
            <span className={styles.corps}>
              <span className={styles.eyebrow}>
                Pull request
                <span className={styles.fleche} aria-hidden="true">
                  →
                </span>
              </span>
              <span className={styles.titre}>{prTitre}</span>
              <span className={styles.sousTitre}>Discussion et commits</span>
            </span>
          </a>
        ) : null}

        {specUrl ? (
          <a
            className={styles.carte}
            href={specUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            <span className={styles.icone}>
              <IconeSpec />
            </span>
            <span className={styles.corps}>
              <span className={styles.eyebrow}>
                Spec
                <span className={styles.fleche} aria-hidden="true">
                  →
                </span>
              </span>
              <span className={styles.titre}>{specTitre}</span>
              <span className={styles.sousTitre}>Sur le tag de release</span>
            </span>
          </a>
        ) : null}
      </div>

      {tickets.length > 0 ? (
        <div className={styles.tickets}>
          <div className={styles.ticketsEntete}>
            <span className={styles.icone} aria-hidden="true">
              <IconeTickets />
            </span>
            <span className={styles.ticketsLabel}>Tickets</span>
            <span className={styles.ticketsCompte}>{tickets.length}</span>
          </div>
          <div className={styles.arbre}>
            <a
              className={styles.noeudRacine}
              href={parent.href}
              target="_blank"
              rel="noopener noreferrer"
            >
              #{parent.number}
            </a>
            {enfants.length > 0 ? (
              <>
                <span className={styles.tronc} aria-hidden="true" />
                <div className={styles.rameau}>
                  {enfants.map((t) => (
                    <div key={t.number} className={styles.branche}>
                      <a
                        className={styles.noeudFeuille}
                        href={t.href}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        #{t.number}
                      </a>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </div>
        </div>
      ) : null}
    </nav>
  );
}
