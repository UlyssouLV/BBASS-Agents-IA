import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  glossaireSidebar: ['glossaire'],
  featuresSidebar: [
    {
      type: 'category',
      label: 'Inspecteur',
      collapsed: false,
      link: {type: 'doc', id: 'features/inspecteur/index'},
      items: [
        'features/inspecteur/connexion',
        'features/inspecteur/apercu',
        {
          type: 'category',
          label: 'Étiquettes',
          collapsed: false,
          items: [
            'features/inspecteur/chat',
            'features/inspecteur/outil',
            'features/inspecteur/extraction-web',
            'features/inspecteur/garde-fous',
            'features/inspecteur/titrage',
            'features/inspecteur/resume-et-profil',
            'features/inspecteur/ocr',
            'features/inspecteur/vision',
          ],
        },
      ],
    },
  ],
  adrSidebar: [
    {
      type: 'category',
      label: 'Architecture Decision Records',
      collapsed: false,
      link: {type: 'doc', id: 'adr/index'},
      items: [
        'adr/0001-backend-local-par-poste',
        'adr/0002-relais-central-mistral',
        'adr/0003-v1-scope-castries-seule',
        'adr/0004-modele-mistral-decide-par-la-vm',
        'adr/0005-compte-administrateur-droit-global',
        'adr/0006-compte-rattache-plusieurs-poles',
        'adr/0007-cle-admin-vm-reutilisee-poste',
        'adr/0008-postgresql-vm-centrale',
        'adr/0009-pieces-jointes-jamais-mistral-files-api',
        'adr/0010-front-poste-react-typescript-vite',
        'adr/0011-gestion-dependances-python-avec-uv',
        'adr/0012-mode-developpeur-cle-admin-vm-tous-comptes',
        'adr/0013-recherche-web-searxng-auto-heberge',
        'adr/0014-recherche-web-en-deux-temps-extraction-isolee',
      ],
    },
  ],
};

export default sidebars;
