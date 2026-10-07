import type {ReactNode} from 'react';

import styles from './apercus.module.css';

// Niveau « Comptes » de PageInspecteur, après une clé acceptée.
export default function ApercuComptes(): ReactNode {
  return (
    <div className={styles.cadre}>
      <h2 className={styles.titre}>Inspecteur des échanges avec le modèle</h2>
      <p className={styles.fil}>
        <strong>Comptes</strong>
      </p>
      <div className={styles.enteteNiveau}>
        <h3>Comptes</h3>
        <button type="button" className={styles.boutonSecondaire}>
          Rafraîchir
        </button>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Identifiant</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <span className={styles.lien}>dupont</span>
            </td>
          </tr>
          <tr>
            <td>
              <span className={styles.lien}>martin</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
