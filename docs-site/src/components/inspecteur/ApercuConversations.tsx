import type {ReactNode} from 'react';

import styles from './apercus.module.css';

export default function ApercuConversations(): ReactNode {
  return (
    <div className={styles.cadre}>
      <h2 className={styles.titre}>Inspecteur des échanges avec le modèle</h2>
      <p className={styles.fil}>
        <span className={styles.lien}>Comptes</span>
        <span aria-hidden="true">/</span>
        <strong>dupont</strong>
      </p>
      <div className={styles.enteteNiveau}>
        <h3>Conversations de dupont</h3>
        <button type="button" className={styles.boutonSecondaire}>
          Rafraîchir
        </button>
      </div>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Titre</th>
            <th>Créée le</th>
            <th>Dernière activité</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <span className={styles.lien}>Recherche PLU Castries</span>
            </td>
            <td>6 oct. 2026, 09:12</td>
            <td>6 oct. 2026, 14:02</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
