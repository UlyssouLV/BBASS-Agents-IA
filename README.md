# BBASS-Agents-IA

Logiciel d'agents IA pour le cabinet de géomètres-experts BBASS. L'objectif est de mettre à disposition des collaborateurs une interface unique donnant accès à plusieurs agents métiers, capables de les assister sur des tâches courantes du cabinet. Le moteur de langage retenu est Mistral AI, choix du cabinet pour des raisons de souveraineté et de sécurité : ce projet ne consiste pas à entraîner une IA, mais à construire les agents et l'application qui les exploite.

## État actuel

Le projet démarre. Le repo ne contient pour l'instant que ce README et la feuille de route du projet. Aucune interface, aucun déploiement et aucun agent opérationnel à ce stade.

## Ce qu'on construit

Une application composée d'un backend Python et d'une interface web (HTML/CSS/JS), avec des comptes par collaborateur. L'interface prend la forme d'une fenêtre de discussion (type chatbot) servant de point d'entrée vers les différents agents métiers. Le logiciel est destiné à être déployé et mis à jour de façon centralisée, pour être utilisé directement sur les postes des agences.

## Agents prévus

- Administration
- Appels d'offres
- Foncier
- DAO
- Urbanisme
- Détection de réseaux

## Priorité du moment

Le travail actuel porte sur l'interface (chat, comptes, accès aux agents) et sur le système de déploiement sur les postes des agences. La configuration fine de chaque agent métier viendra dans un second temps.

## Suite

Le développement des agents métiers eux-mêmes suivra, une fois l'interface et le déploiement en place.
