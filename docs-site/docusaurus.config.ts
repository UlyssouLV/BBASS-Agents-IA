import {createRequire} from 'node:module';
import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const require = createRequire(import.meta.url);
const remarkGlossaire = require('./src/remark/glossaire.cjs');

const config: Config = {
  title: 'BBASS Agents IA',
  tagline: 'Documentation du projet — produit, features et décisions d’architecture',
  favicon: 'img/favicon.ico',

  url: 'https://ulyssoulv.github.io',
  baseUrl: '/BBASS-Agents-IA/',

  organizationName: 'UlyssouLV',
  projectName: 'BBASS-Agents-IA',

  onBrokenLinks: 'warn',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },

  i18n: {
    defaultLocale: 'fr',
    locales: ['fr'],
  },

  plugins: [
    function watchPollingPlugin() {
      return {
        name: 'watch-polling-network-drive',
        configureWebpack() {
          return {
            watchOptions: {
              poll: 1000,
              aggregateTimeout: 300,
            },
          };
        },
      };
    },
  ],

  presets: [
    [
      'classic',
      {
        docs: {
          path: '../docs',
          routeBasePath: 'docs',
          sidebarPath: './sidebars.ts',
          numberPrefixParser: false,
          beforeDefaultRemarkPlugins: [remarkGlossaire],
          exclude: [
            'suivi-avancement/**',
            'specs/**',
            'dev/**',
            'img/**',
            'architecture/**',
            'changelog/README.md',
            'feuille-de-route/README.md',
            'bugs/README.md',
          ],
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      defaultMode: 'light',
      disableSwitch: true,
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: '',
      logo: {
        alt: 'BBASS Agents IA',
        src: 'img/logo-bbass-agents-ia.jpg',
      },
      items: [
        {
          to: '/',
          label: 'Accueil',
          position: 'left',
          className: 'navbar-accueil',
        },
        {
          type: 'docSidebar',
          sidebarId: 'featuresSidebar',
          position: 'left',
          label: 'Features',
        },
        {
          type: 'docSidebar',
          sidebarId: 'changelogSidebar',
          position: 'left',
          label: 'Changelog',
        },
        {
          type: 'docSidebar',
          sidebarId: 'bugsSidebar',
          position: 'left',
          label: 'Bugs',
        },
        {
          type: 'docSidebar',
          sidebarId: 'adrSidebar',
          position: 'left',
          label: 'ADR',
        },
        {
          type: 'doc',
          docId: 'glossaire',
          position: 'left',
          label: 'Glossaire',
        },
        {
          href: 'https://github.com/UlyssouLV/BBASS-Agents-IA',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'light',
      copyright: `BBASS — doc Agents IA.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
