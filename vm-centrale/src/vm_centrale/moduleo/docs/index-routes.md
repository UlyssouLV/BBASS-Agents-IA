# Routes GET de l'API Moduléo

Généré par `scripts/telecharger_doc_moduleo.py` depuis `wadl.xml` et `documentation.html` (téléchargés le 2026-10-07) : ne pas modifier à la main. 207 routes GET, préfixées par `MODULEO_URL`.

## Activite

| Route | Paramètres | Description |
| --- | --- | --- |
| `planning/activite` | — | Récupère l'ensemble des activités. |
| `planning/activite/{idActivite}` | `idActivite` (int) | Récupère une activité en fonction de son identifiant unique. |
| `planning/activite/{idActivite}/etatsactivite` | `idActivite` (int) | Récupère un ensemble d'identifiants uniques d'états activité en fonction de l'identifiant unique de l'activité. |

## ActiviteEtat

| Route | Paramètres | Description |
| --- | --- | --- |
| `planning/activiteetat/multi?ids={ids}` | `ids` (string) | Récupère un ensemble d'états activité en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `planning/activiteetat/{idActiviteEtat}` | `idActiviteEtat` (int) | Récupère un etat activité en fonction de son identifiant unique. |

## Adresse

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/adresse/{idAdresse}` | `idAdresse` (int) | Récupère l'adresse postale en fonction de son identifiant unique. |

## Affaire

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/affaire/multi?ids={ids}` | `ids` (string) | Récupère un ensemble d'affaires en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/affaire/numeroAffaire/{numAffaire}` | `numAffaire` (string) | Récupère l' identifiant unique d'une affaire en fonction du numéro de l'affaire. |
| `cogeo/affaire/numeroAffaire?numAffaire={numAffaire}` | `numAffaire` (string) | Récupère l' identifiant unique d'une affaire en fonction du numéro de l'affaire. |
| `cogeo/affaire/{idAffaire}` | `idAffaire` (int) | Récupère une affaire en fonction son identifiant unique. |
| `cogeo/affaire/{idAffaire}/avoirs` | `idAffaire` (int) | Récupère les identifiants uniques des avoirs d'une affaire. |
| `cogeo/affaire/{idAffaire}/centroide` | `idAffaire` (int) | Récupère l'identifiant unique du localisant centroïde d'une affaire. |
| `cogeo/affaire/{idAffaire}/champsspecifiques` | `idAffaire` (int) | Récupère les identifiants uniques des champs spécifiques d'une affaire. |
| `cogeo/affaire/{idAffaire}/devis` | `idAffaire` (int) | Récupère les identifiants uniques des devis d'une affaire. |
| `cogeo/affaire/{idAffaire}/elementsged` | `idAffaire` (int) | Récupère les identifiants uniques des fichiers GED d'une affaire. |
| `cogeo/affaire/{idAffaire}/factures` | `idAffaire` (int) | Récupère les identifiants uniques des factures d'une affaire. |
| `cogeo/affaire/{idAffaire}/frais` | `idAffaire` (int) | Récupère les identifiants uniques des frais d'une affaire. |
| `cogeo/affaire/{idAffaire}/groupesutilisateur` | `idAffaire` (int) | Récupère les identifiants uniques des groupes utilisateurs d'une affaire selon son identifiant unique. |
| `cogeo/affaire/{idAffaire}/intervenants` | `idAffaire` (int) | Récupère les intervenants d'une affaire. |
| `cogeo/affaire/{idAffaire}/localisantsadditionnels` | `idAffaire` (int) | Récupère les identifiants uniques des localisants additionnels d'une affaire. |
| `cogeo/affaire/{idAffaire}/operations` | `idAffaire` (int) | Récupère les opérations d'une affaire. |
| `cogeo/affaire/{idAffaire}/parcelles` | `idAffaire` (int) | Récupère les identifiants uniques des parcelles d'une affaire. |
| `cogeo/affaire/{idAffaire}/polygones` | `idAffaire` (int) | Récupère les polygones d'emprise d'une affaire selon son identifiant unique au format LT93. |
| `cogeo/affaire/{idAffaire}/procedureapplication` | `idAffaire` (int) | Récupère la procédure application de l'affaire. |
| `cogeo/affaire/{idAffaire}/tempspasses` | `idAffaire` (int) | Récupère les identifiants uniques des temps passés d'une affaire. |
| `cogeo/affaire?texte={texte}&idDossierProduction={idDossierProduction}&etatAffaire={etatAffaire}&dateCreationMin={dateCreationMin}&dateCreationMax={dateCreationMax}&dateOuvertureMin={dateOuvertureMin}&dateOuvertureMax={dateOuvertureMax}&dateLivraisonMin={dateLivraisonMin}&dateLivraisonMax={dateLivraisonMax}&dateClotureMin={dateClotureMin}&dateClotureMax={dateClotureMax}&idsSite={idsSite}&idsService={idsService}&idsResponsable={idsResponsable}&idsActeurEnCharge={idsActeurEnCharge}&nbMaxResultats={nbMaxResultats}` | `texte` (string), `idDossierProduction` (int), `etatAffaire` (string), `dateCreationMin` (string), `dateCreationMax` (string), `dateOuvertureMin` (string), `dateOuvertureMax` (string), `dateLivraisonMin` (string), `dateLivraisonMax` (string), `dateClotureMin` (string), `dateClotureMax` (string), `idsSite` (string), `idsService` (string), `idsResponsable` (string), `idsActeurEnCharge` (string), `nbMaxResultats` (int) | Récupère les identifiants uniques d'un ensemble d'affaires en fonction des paramètres. |

## Arborescence

| Route | Paramètres | Description |
| --- | --- | --- |
| `fileo/arborescence` | — | Récupère l'ensemble des identifiants uniques des arborescences. |
| `fileo/arborescence/multi?ids={ids}` | `ids` (string) | Récupère un ensemble d'arborescences en fonction d'une liste d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `fileo/arborescence/{idArborescence}` | `idArborescence` (int) | Récupère une arborescence en fonction de son identifiant unique. |

## Archive

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/archive/{idArchive}` | `idArchive` (int) | Récupère une archive en fonction de son identifiant unique. |

## Article

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/article/multi?ids={ids}` | `ids` (string) | Récupère un ensemble d'articles en fonction d'une liste d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/article/{idArticle}` | `idArticle` (int) | Récupère un article en fonction de son identifiant unique. |
| `cogeo/article?texte={texte}&idsFamilleArticle={idsFamilleArticle}&modeFiltrationFamille={modeFiltrationFamille}&idsMarche={idsMarche}&modeFiltrationMarche={modeFiltrationMarche}&nombreMaxResultats={nombreMaxResultats}` | `texte` (string), `idsFamilleArticle` (string), `modeFiltrationFamille` (string), `idsMarche` (string), `modeFiltrationMarche` (string), `nombreMaxResultats` (int) | Récupère les identifiants uniques d'un ensemble d'articles en fonction des paramètres. |

## Auth

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/auth/droits` | — | Récupère les droits liés à la clé d'API en cours d'utilisation. |
| `moduleo/auth/identification/{login}/{password}` | `login` (string), `password` (string) | Obtient le code personnel lié à la clé d'API en utilisant son identifant Moduleo ou lance la demande d'indentification en cas d'authentification double facteurs |
| `moduleo/auth/identification?login={login}&password={password}` | `login` (string), `password` (string) | Obtient le code personnel lié à la clé d'API en utilisant son identifant Moduleo ou lance la demande d'indentification en cas d'authentification double facteurs |
| `moduleo/auth/identificationdoubleauth/{login}/{password}/{code}` | `login` (string), `password` (string), `code` (string) | Sans description dans la page de documentation. |
| `moduleo/auth/identificationdoubleauth?login={login}&password={password}&code={code}` | `login` (string), `password` (string), `code` (string) | Sans description dans la page de documentation. |
| `moduleo/auth/login` | — | Obtient le code personnel lié à la clé d'API en utilisant son identifiant Moduleo ou lance la demande d'identification en cas d'authentification double facteurs. |
| `moduleo/auth/validite/{key}/{codeTmp}` | `key` (string), `codeTmp` (string) | Permet de tester la validité d'une clé d'API. |

## Avoir

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/avoir/facture?idFacture={idFacture}` | `idFacture` (int) | Récupère les identifiants uniques d'un ensemble d'avoirs en fonction de l'identifiant unique d'une facture. |
| `cogeo/avoir/multi?ids={ids}` | `ids` (string) | Récupère un ensemble d'avoirs en fonction d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/avoir/{idAvoir}` | `idAvoir` (int) | Récupère un avoir en fonction de son identifiant unique. |
| `cogeo/avoir?texte={texte}&emise={emise}&dateEmissionMin={dateEmissionMin}&dateEmissionMax={dateEmissionMax}&idsService={idsService}&idsResponsable={idsResponsable}&idsRedacteur={idsRedacteur}` | `texte` (string), `emise` (boolean), `dateEmissionMin` (string), `dateEmissionMax` (string), `idsService` (string), `idsResponsable` (string), `idsRedacteur` (string) | Récupère les identifiants uniques d'un ensemble d'avoirs en fonction des paramètres. |

## Banque

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/banque/{idBanque}` | `idBanque` (int) | Récupère une banque en fonction de son identifiant unique. |

## CategorieNote

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/categorienote/{idCategorieNote}` | `idCategorieNote` (int) | Récupère la catégorie de note en fonction de son identifiant unique. |

## CategorieTacheAFaire

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/categorietacheafaire/{idCategorieTacheAFaire}` | `idCategorieTacheAFaire` (int) | Récupère la catégorie de tâche à faire en fonction de son identifiant unique. |

## ChampSpecifique

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/champspecifique/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de champ spécifique en fonction d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/champspecifique/{idChampSpecifique}` | `idChampSpecifique` (int) | Récupère un champ spécifique en fonction son identifiant unique. |

## ChampSpecifiqueDefinition

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/champspecifiquedefinition` | — | Récupère la liste des identifiants uniques des définitions des champs spécifiques. |
| `cogeo/champspecifiquedefinition/{idDefinition}` | `idDefinition` (int) | Récupère une définition de champ spécifique en fonction de son identifiant unique. |
| `cogeo/champspecifiquedefinition/{idDefinition}/services` | `idDefinition` (int) | Récupère les identifiants uniques des services d'une définition du champ spécifique. |

## CodeActivite

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/codeactivite` | — | Récupère l'ensemble des identifiants uniques des codes activités. |
| `cogeo/codeactivite/{idCodeActivite}` | `idCodeActivite` (int) | Récupère un code activité en fonction de son identifiant unique. |

## CoefficientActualisation

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/coefactualisation/{idCoefficientActualisation}` | `idCoefficientActualisation` (int) | Récupère un coefficiant d'actualisation en fonction de son identifiant unique. |

## Commune

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/commune/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de communes en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `moduleo/commune/{idCommune}` | `idCommune` (int) | Récupère une commune en fonction de son identifiant unique. |
| `moduleo/commune?nom={nom}&codePostal={codePostal}&codeInsee={codeInsee}&nbMaxResultat={nbMaxResultat}` | `nom` (string), `codePostal` (string), `codeInsee` (string), `nbMaxResultat` (int) | Récupère les identifiants uniques d'un ensemble de communes en fonction des paramètres. |

## Contact

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/contact/collectivite/{idContact}` | `idContact` (int) | Récupère une collectivité en fonction de l'identifiant unique du contact. |
| `cogeo/contact/contactlie/multi?ids={ids}` | `ids` (string) | Récupère un contact lié en fonction de son identifiant unique. |
| `cogeo/contact/contactlie/{idContactLie}` | `idContactLie` (int) | Récupère un contact lié en fonction de son identifiant unique. |
| `cogeo/contact/groupecontacts/{idContact}` | `idContact` (int) | Récupère un groupe de contacts en fonction de l'identifiant unique du contact. |
| `cogeo/contact/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de contact en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/contact/personne/{idContact}` | `idContact` (int) | Récupère une personne en fonction de l'identifiant unique du contact. |
| `cogeo/contact/personnemorale/{idContact}` | `idContact` (int) | Récupère une personne morale en fonction de l'identifiant unique du contact. |
| `cogeo/contact/societe/{idContact}` | `idContact` (int) | Récupère une société en fonction de l'identifiant unique du contact. |
| `cogeo/contact/{idContact}` | `idContact` (int) | Récupère un contact en fonction de son identifiant unique. |
| `cogeo/contact/{idContact}/adresses` | `idContact` (int) | Récupère l'ensemble des identifiants uniques des adresses postales du contact. |
| `cogeo/contact/{idContact}/affaireintervenant` | `idContact` (int) | Récupère un ensemble d'identifiants uniques d'affaires dont le contact passé en paramètre est intervenant. |
| `cogeo/contact/{idContact}/affaires` | `idContact` (int) | Récupère un ensemble d'identifiants uniques d'affaires dont le contact passé en paramètre est client. |
| `cogeo/contact/{idContact}/emails` | `idContact` (int) | Récupère l'ensemble des identifiants uniques des adresses email du contact. |
| `cogeo/contact/{idContact}/notes` | `idContact` (int) | Récupère l'ensemble des identifiants uniques des notes du contact. |
| `cogeo/contact/{idContact}/telephones` | `idContact` (int) | Récupère l'ensemble des identifiants uniques des numéros de téléphone du contact. |
| `cogeo/contact?texte={texte}&typeContact={typeContact}&typeDonneurOrdreGE={typeDonneurOrdreGE}&idsQualifications={idsQualifications}&nbMaxResultat={nbMaxResultat}` | `texte` (string), `typeContact` (string), `typeDonneurOrdreGE` (string), `idsQualifications` (string), `nbMaxResultat` (int) | Récupère les identifiants uniques d'un ensemble de contacts en fonction des paramètres. |

## Destinataire

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/destinataire/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de destinataires en fonction d'une liste d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/destinataire/{idDestinataire}` | `idDestinataire` (int) | Récupère un destinataire en fonction de son identifiant unique. |

## Devis

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/devis/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de devis / contrat en fonction d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/devis/{idDevis}` | `idDevis` (int) | Récupère un devis / contrat en fonction de son identifiant unique. |
| `cogeo/devis/{idDevis}/factures` | `idDevis` (int) | Récupère les identifiants uniques d'un ensemble de facture en fonction de l'identifiant unique d'un devis / contrat. |
| `cogeo/devis?texte={texte}&emis={emis}&dateEmissionMin={dateEmissionMin}&dateEmissionMax={dateEmissionMax}&idsService={idsService}&idsResponsable={idsResponsable}&idsRedacteur={idsRedacteur}&dateReponseMin={dateReponseMin}&dateReponseMax={dateReponseMax}&etat={etat}` | `texte` (string), `emis` (boolean), `dateEmissionMin` (string), `dateEmissionMax` (string), `idsService` (string), `idsResponsable` (string), `idsRedacteur` (string), `dateReponseMin` (string), `dateReponseMax` (string), `etat` (string) | Récupère les identifiants uniques d'un ensemble de devis / contrat en fonction des paramètres. |

## Dossier

| Route | Paramètres | Description |
| --- | --- | --- |
| `fileo/dossier/{idDossier}` | `idDossier` (int) | Récupère un dossier en fonction de son identifiant unique. |
| `fileo/dossier/{idDossier}/dossiersenfants` | `idDossier` (int) | Récupère les identifiants uniques des sous-dossiers selon l'identifiant unique du dossier. |
| `fileo/dossier/{idDossier}/fichiersenfants` | `idDossier` (int) | Récupère les identifiants uniques des fichiers selon l'identifiant unique du dossier. |

## DossierPartage

| Route | Paramètres | Description |
| --- | --- | --- |
| `fileo/dossierpartage/{idDossierPartage}` | `idDossierPartage` (int) | Récupère un dossier partagé en fonction de son identifiant unique. |

## DossierProduction

| Route | Paramètres | Description |
| --- | --- | --- |
| `fileo/dossierproduction/numero?numero={numero}` | `numero` (string) | Recherche un dossier de production à partir de son numéro |
| `fileo/dossierproduction/{idDossierProduction}` | `idDossierProduction` (int) | Récupère un dossier de production en fonction de son identifiant unique. |
| `fileo/dossierproduction/{idDossierProduction}/dossiersenfants` | `idDossierProduction` (int) | Récupère les identifiants uniques des dossiers enfants en fonction de l'identifiant unique du dossier de production. |
| `fileo/dossierproduction/{idDossierProduction}/fichiersenfants` | `idDossierProduction` (int) | Récupère les identifiants uniques des fichiers enfants en fonction de l'identifiant unique du dossier de production. |
| `fileo/dossierproduction?texteRecherche={texteRecherche}` | `texteRecherche` (string) | Recherche un ou des dossiers de production à partir d'un texte |

## Echeance

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/echeance/{idEcheance}` | `idEcheance` (int) | Récupère une échéance de facturation en fonction de son identifiant unique. |

## ElementGed

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/elementged/courrier/{idCourrier}` | `idCourrier` (int) | Récupère un courrier de la GED en fonction de son identifiant unique. |
| `cogeo/elementged/document/{idDocument}` | `idDocument` (int) | Récupère un document de la GED en fonction de son identifiant unique. |
| `cogeo/elementged/email/{idEmail}` | `idEmail` (int) | Récupère un email de la GED en fonction de son identifiant unique. |
| `cogeo/elementged/plan/{idPlan}` | `idPlan` (int) | Récupère un plan de la GED en fonction de son identifiant unique. |
| `cogeo/elementged/{idElementGed}` | `idElementGed` (int) | Récupère un élément de la GED en fonction de son identifiant unique. |
| `cogeo/elementged/{idElementGed}/download` | `idElementGed` (int) | Télécharge un fichier de la GED en fonction de son identifiant unique. |

## Email

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/email/{idEmail}` | `idEmail` (int) | Récupère un email en fonction de son identifiant unique. |

## Enveloppe

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/enveloppe/{idEnveloppePrevisionnelle}` | `idEnveloppePrevisionnelle` (int) | Récupère une enveloppe prévisionnelle en fonction de son identifiant unique. |

## Equipement

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/equipement` | — | Récupère l'ensemble des identifiants uniques des équipements. |
| `moduleo/equipement/{idEquipement}` | `idEquipement` (int) | Récupère un équipement en fonction de son identifiant unique. |

## EtatPresence

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/etatpresence/multi?ids={ids}` | `ids` (string) | Récupère un enssemble d'états de présence en fonction d'un ensemble d'dentifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/etatpresence/{idEtatPresence}` | `idEtatPresence` (int) | Récupère l'état de présence en fonction de son identifiant unique. |

## ExpressionNumeroAutoArchive

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/numautoarchive/{idExpressionNumeroAutoArchive}` | `idExpressionNumeroAutoArchive` (int) | Récupère un modele de numérotation des archives en fonction de son identifiant unique. |

## Facture

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/facture/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de factures en fonction d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/facture/{idFacture}` | `idFacture` (int) | Récupère une facture en fonction de son identifiant unique. |
| `cogeo/facture/{idFacture}/devis` | `idFacture` (int) | Récupère un ensemble d'identifiants uniques de devis en fonction de l'identifiant unique d'une facture. |
| `cogeo/facture/{idFacture}/frais` | `idFacture` (int) | Récupère un ensemble d'identifiants uniques de frais en fonction de l'identifiant unique d'une facture. |
| `cogeo/facture/{idFacture}/tempspasses` | `idFacture` (int) | Récupère un ensemble d'identifiants uniques de temps passés en fonction de l'identifiant unique d'une facture. |
| `cogeo/facture?texte={texte}&emise={emise}&dateEmissionMin={dateEmissionMin}&dateEmissionMax={dateEmissionMax}&idsService={idsService}&idsResponsable={idsResponsable}&idsRedacteur={idsRedacteur}` | `texte` (string), `emise` (boolean), `dateEmissionMin` (string), `dateEmissionMax` (string), `idsService` (string), `idsResponsable` (string), `idsRedacteur` (string) | Récupère les identifiants uniques d'un ensemble de factures en fonction des paramètres. |

## FamilleArticles

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/famillearticles` | — | Récupère l'ensemble des identifiants uniques des familles d'articles |
| `cogeo/famillearticles/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de familles d'articles à partir d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/famillearticles/{idFamilleArticles}` | `idFamilleArticles` (int) | Récupère la famille d'articles en fonction de son identifiant unique. |

## Fichier

| Route | Paramètres | Description |
| --- | --- | --- |
| `fileo/fichier/multi/download?ids={ids}` | `ids` (string) | Télécharge un ensemble de fichiers en fonction d'un ensemble d'identifiant unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `fileo/fichier/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de fichiers en fonction de son identifiant unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `fileo/fichier/{idFichier}` | `idFichier` (int) | Récupère un fichier en fonction de son identifiant unique. |
| `fileo/fichier/{idFichier}/download` | `idFichier` (int) | Télécharge un fichier en fonction de son identifiant unique. |

## Frais

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/frais/{idFrais}` | `idFrais` (int) | Récupère un frais en fonction de son identifiant unique. |
| `cogeo/frais?dateMin={dateMin}&dateMax={dateMax}&idsUtilisateurs={idsUtilisateurs}&idTypeFrais={idTypeFrais}&idAffaire={idAffaire}&nbMaxResultat={nbMaxResultat}` | `dateMin` (string), `dateMax` (string), `idsUtilisateurs` (string), `idTypeFrais` (int), `idAffaire` (int), `nbMaxResultat` (int) | Récupère les identifiants uniques d'un ensemble de frais en fonction des paramètres. |

## Gabarit

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/gabarit/devis` | — | Récupère l'ensemble des identifiants uniques des gabarits de devis. |
| `cogeo/gabarit/devis/defaut` | — | Récupère l'identifiant unique du gabarits de devis par défaut. |
| `cogeo/gabarit/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de gabarits en fonction d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/gabarit/{idGabarit}` | `idGabarit` (int) | Récupère un gabarit en fonction de son identifiant unique. |

## Groupe

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/groupe/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de groupes d'affaires en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/groupe/{idGroupe}` | `idGroupe` (int) | Récupère un groupe d'affaires en fonction de son identifiant unique. |
| `cogeo/groupe/{idGroupe}/affaires` | `idGroupe` (int) | Récupère la liste des identifiants uniques des affaires d'un groupe en fonction de son identifiant unique. |
| `cogeo/groupe?texte={texte}` | `texte` (string) | Récupère les identifiants uniques d'un ensemble de groupes d'affaires en fonction des paramètres. |

## GroupeUtilisateur

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/groupeutilisateur/{idGroupeUtilisateur}` | `idGroupeUtilisateur` (int) | Récupère un groupe utilisateur en fonction de son identifiant unique. |

## Intervenant

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/intervenant/multi?ids={ids}` | `ids` (string) | Récupère un ensemble d'intervenants en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/intervenant/{idIntervenant}` | `idIntervenant` (int) | Récupère un intervenant en fonction son identifiant unique. |

## JourFerie

| Route | Paramètres | Description |
| --- | --- | --- |
| `planning/jourferie` | — | Récupère l'ensemble des identifiants uniques des jours fériés |
| `planning/jourferie/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de jours fériés à partir d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `planning/jourferie/{idJourFerie}` | `idJourFerie` (int) | Récupère un jour férié à partir de son identifiant unique |

## Licence

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/licence/achat` | — | Récupère l'ensemble des licences. |
| `moduleo/licence/location` | — | Récupère l'ensemble des licences. |

## Lieu

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/lieu` | — | Récupère l'ensemble des identifiants uniques des lieux. |
| `cogeo/lieu/{idLieu}` | `idLieu` (int) | Récupère un lieu en fonction de son identifiant unique. |

## LigneArticle

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/lignearticle/multi/mo?ids={ids}` | `ids` (string) | Récupère un ensemble de lignes article MO en fonction d'une liste d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/lignearticle/multi/standard?ids={ids}` | `ids` (string) | Récupère un ensemble de lignes article standard en fonction d'une liste d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/lignearticle/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de lignes article en fonction d'une liste d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/lignearticle/{idLigneArticle}` | `idLigneArticle` (int) | Récupère une ligne article en fonction de son identifiant unique. |
| `cogeo/lignearticle/{idLigneArticle}/mo` | `idLigneArticle` (int) | Récupère une ligne article MO en fonction de son identifiant unique. |
| `cogeo/lignearticle/{idLigneArticle}/standard` | `idLigneArticle` (int) | Récupère une ligne article standard en fonction de son identifiant unique. |

## Localisant

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/localisant/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de localisants en fonction d'une liste d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/localisant/{idLocalisant}` | `idLocalisant` (int) | Récupère un localisant en fonction de son identifiant unique. |

## Marche

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/marche/{idMarche}` | `idMarche` (int) | Récupère un marché en fonction de son identifiant unique. |

## ModeReglement

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/modeReglement/{idModeReglement}` | `idModeReglement` (int) | Récupère un mode de règlement en fonction de son identifiant unique. |

## Note

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/note/{idNote}` | `idNote` (int) | Récupère une note en fonction de son identifiant unique. |

## Operation

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/operation/{idOperation}` | `idOperation` (int) | Récupère l'opération liée d'une parcelle en fonction de son identifiant unique. |
| `cogeo/operation/{idOperation}/etatspresence` | `idOperation` (int) | Récupère les identifiants uniques de états de présence liées de l'opération. |
| `cogeo/operation/{idOperation}/parcellescibles` | `idOperation` (int) | Récupère les identifiants uniques de parcelles cibles de l'opération. |
| `cogeo/operation/{idOperation}/parcellesliees` | `idOperation` (int) | Récupère les identifiants uniques de parcelles liées de l'opération. |

## Parcelle

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/parcelle/{idParcelle}` | `idParcelle` (int) | Récupère une parcelle en fonction de son identifiant unique. |
| `cogeo/parcelle/{idParcelle}/operationscibles` | `idParcelle` (int) | Récupère les identifiants uniques d'un ensemble d'opérations dont la parcelle est cible en fonction de l'identifiant unique de la parcelle. |
| `cogeo/parcelle/{idParcelle}/operationsliees` | `idParcelle` (int) | Récupère les identifiants uniques d'un ensemble d'opérations liées d'une parcelle en fonction de l'identifiant unique de la parcelle. |
| `cogeo/parcelle/{idParcelle}/parcellesfille` | `idParcelle` (int) | Récupère les identifiants uniques d'un ensemble de parcelles filles d'une parcelle en fonction l'identifiant unique de la parcelle mère. |
| `cogeo/parcelle/{idParcelle}/proprietaires` | `idParcelle` (int) | Récupère les identifiants uniques d'un ensemble de propriétaires d'une parcelle en fonction de l'identifiant unique de la parcelle. |
| `cogeo/parcelle/{idParcelle}/titres` | `idParcelle` (int) | Récupère les identifiants uniques d'un ensemble de titre d'une parcelle en fonction de l'identifiant unique de la parcelle. |

## Phase

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/phase/{idPhase}` | `idPhase` (int) | Récupère une phase en fonction de son identifiant unique. |

## ProcedureApplication

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/procedureapplication/{idProcedureApplication}` | `idProcedureApplication` (int) | Récupère une procédure application en fonction de son identifiant unique. |
| `cogeo/procedureapplication/{idProcedureApplication}/tachesapplication` | `idProcedureApplication` (int) | Récupère les identifiants uniques des tâches application d'une procédure application. |

## ProcedureDefinition

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/proceduredefinition/{idProcedureDefinition}` | `idProcedureDefinition` (int) | Récupère une procédure définition en fonction de son identifiant unique. |
| `cogeo/proceduredefinition/{idProcedureDefinition}/tachesdefinition` | `idProcedureDefinition` (int) | Récupère les identifiants uniques des tâches définition d'une procédure définition. |

## ProcedureDefinitionDocument

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/document/{idDocument}` | `idDocument` (int) | Récupère un document en fonction de son identifiant unique. |

## ProcedureTacheApplication

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/proceduretacheapplication/{idTacheApplication}` | `idTacheApplication` (int) | Récupère une tâche application en fonction de son identifiant unique. |
| `cogeo/proceduretacheapplication/{idTacheApplication}/tachesapplications` | `idTacheApplication` (int) | Récupère la liste des sous-tâches application en fonction de l'identifiant unique de la tâche application. |

## ProcedureTacheDefinition

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/proceduretachedefinition/{idTacheDefinition}` | `idTacheDefinition` (int) | Récupère une tâche définition en fonction de son identifiant unique. |
| `cogeo/proceduretachedefinition/{idTacheDefinition}/tachesdefinitions` | `idTacheDefinition` (int) | Récupère la liste des sous-tâche définition en fonction de l'identifiant unique de la tâche application. |

## Proprietaire

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/proprietaire/{idProprietaire}` | `idProprietaire` (int) | Récupère le propriétaire d'une parcelle en fonction de son identifiant unique. |

## Qualification

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/qualification/all` | — | Récupère l'ensemble des qualifications. |
| `cogeo/qualification/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de qualifications en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/qualification/{idQualification}` | `idQualification` (int) | Récupère une qualification de contact en fonction de son identifiant unique. |

## RH

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/ressourceshumaines/{idUtilisateur}` | `idUtilisateur` (int) | Récupère les informations personnelles d'un utilisateur en fonction de son identifiant unique. |

## Recurrence

| Route | Paramètres | Description |
| --- | --- | --- |
| `planning/recurrence/{idRecurrenceGroupeTache}` | `idRecurrenceGroupeTache` (int) | Récupère une récurrence de groupe de tâche en fonction son identifiant unique. |

## Reglement

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/reglement/{idReglement}` | `idReglement` (int) | Récupère un règlement en fonction de son identifiant unique. |

## Service

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/service/{idService}` | `idService` (int) | Récupère un service en fonction de son identifiant unique. |
| `moduleo/service?nom={nom}&actifSeulement={actifSeulement}` | `nom` (string), `actifSeulement` (boolean) | Récupère les identifiants uniques d'un ensemble de services en fonction des paramètres. |

## Site

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/site/{idSite}` | `idSite` (int) | Récupère un site en fonction de son identifiant unique. |
| `moduleo/site?nom={nom}&actifSeulement={actifSeulement}` | `nom` (string), `actifSeulement` (boolean) | Récupère les identifiants uniques d'un ensemble de sites en fonction des paramètres. |

## TacheAFaire

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/tacheafaire/user/{idUser}` | `idUser` (int) | Récupère les identifiants uniques d'un ensemble de tâches à faire en fonction de l'identifiant unique de l'utilisateur. |
| `moduleo/tacheafaire/{idTacheAFaire}` | `idTacheAFaire` (int) | Récupère une tâche à faire en fonction de son identifiant unique. |

## TachePlanning

| Route | Paramètres | Description |
| --- | --- | --- |
| `planning/tacheplanning/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de tâches planning en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `planning/tacheplanning/{idTachePlanning}` | `idTachePlanning` (int) | Récupère une tâche du planning en fonction son identifiant unique. |
| `planning/tacheplanning?libelle={libelle}&remarque={remarque}&idActivite={idActivite}&idsParticipants={idsParticipants}&idsMateriels={idsMateriels}&dateDebut={dateDebut}&dateFin={dateFin}&aUneHeureDebut={aUneHeureDebut}&aUneHeureFin={aUneHeureFin}&idsSites={idsSites}&dateCreationDebut={dateCreationDebut}&dateCreationFin={dateCreationFin}&dateModificationDebut={dateModificationDebut}&dateModificationFin={dateModificationFin}&recupererTachesSupprimees={recupererTachesSupprimees}` | `libelle` (string), `remarque` (string), `idActivite` (int), `idsParticipants` (string), `idsMateriels` (string), `dateDebut` (string), `dateFin` (string), `aUneHeureDebut` (boolean), `aUneHeureFin` (boolean), `idsSites` (string), `dateCreationDebut` (string), `dateCreationFin` (string), `dateModificationDebut` (string), `dateModificationFin` (string), `recupererTachesSupprimees` (boolean) | Récupère les identifiants uniques d'un ensemble de tâches du planning en fonction des paramètres. |

## TacheRemplacement

| Route | Paramètres | Description |
| --- | --- | --- |
| `planning/tacheremplacement/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de tâches remplacement en fonction d'un ensemble identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `planning/tacheremplacement/{idTacheRemplacement}` | `idTacheRemplacement` (int) | Récupère une tâche de remplacement en fonction son identifiant unique. |

## Telephone

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/telephone/{idTelephone}` | `idTelephone` (int) | Récupère un numéro de téléphone en fonction de son identifiant unique. |

## TempsPasse

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/tempspasse/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de temps passé en fonction d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/tempspasse/{idTempsPasse}` | `idTempsPasse` (int) | Récupère un temps passé en fonction de son identifiant unique. |
| `cogeo/tempspasse?dateMin={dateMin}&dateMax={dateMax}&idsUtilisateurs={idsUtilisateurs}&idCodeActivite={idCodeActivite}&idAffaire={idAffaire}&nbMaxResultat={nbMaxResultat}` | `dateMin` (string), `dateMax` (string), `idsUtilisateurs` (string), `idCodeActivite` (int), `idAffaire` (int), `nbMaxResultat` (int) | Récupère les identifiants uniques d'un ensemble de temps passés en fonction des paramètres. |

## Titre

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/titre/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de titre en fonction d'un ensemble d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/titre/{idTitre}` | `idTitre` (int) | Récupère un titre en fonction de son identifiant unique. |

## Tva

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/tva` | — | Récupère l'ensemble des identifiants uniques des TVA. |
| `cogeo/tva/multi?ids={ids}` | `ids` (string) | Récupère un ensemble de TVA en fonction d'une liste d'identifiants unique. Séparateur entre les ids : ',' (virgule). Limite de 200 éléments. |
| `cogeo/tva/{idTva}` | `idTva` (int) | Récupère une TVA en fonction de son identifiant unique. |

## TypeFrais

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/typefrais` | — | Récupère l'ensemble des identifiants uniques des types de frais. |
| `cogeo/typefrais/{idTypeFrais}` | `idTypeFrais` (int) | Récupère un type de frais en fonction de son identifiant unique. |

## Utilisateur

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/utilisateur/utilisateurencours` | — | Récupère l'utilisateur en cours en fonction de sa clé d'API et de son code |
| `moduleo/utilisateur/{idUtilisateur}` | `idUtilisateur` (int) | Récupère un utilisateur par son identifiant unique. |
| `moduleo/utilisateur/{idUtilisateur}/groupes` | `idUtilisateur` (int) | Récupère les identifiants uniques des groupes dont l'utilisateur fait partie. |
| `moduleo/utilisateur?nom={nom}&prenom={prenom}&actifSeulement={actifSeulement}` | `nom` (string), `prenom` (string), `actifSeulement` (boolean) | Récupère les identifiants uniques d'un ensemble d'utilisateurs en fonction des paramètres. |

## UtilisateurCogeo

| Route | Paramètres | Description |
| --- | --- | --- |
| `cogeo/utilisateurcogeo/utilisateur/{idUtilisateur}` | `idUtilisateur` (int) | Récupère une utilisateur cogeo en fonction de son identifiant unique. |
| `cogeo/utilisateurcogeo/{idUtilisateurCogeo}` | `idUtilisateurCogeo` (int) | Récupère une utilisateur cogeo en fonction de son identifiant unique. |

## UtilisateurPlanning

| Route | Paramètres | Description |
| --- | --- | --- |
| `planning/utilisateurplanning/utilisateur/{idUtilisateur}` | `idUtilisateur` (int) | Récupère une utilisateur planning en fonction de son identifiant unique. |
| `planning/utilisateurplanning/{idUtilisateurPlanning}` | `idUtilisateurPlanning` (int) | No documentation available. |

## Vehicule

| Route | Paramètres | Description |
| --- | --- | --- |
| `moduleo/vehicule` | — | Récupère l'ensemble des identifiants uniques des véhicules. |
| `moduleo/vehicule/{idVehicule}` | `idVehicule` (int) | Récupère un véhicule en fonction de son identifiant unique. |

## Webhook

| Route | Paramètres | Description |
| --- | --- | --- |
| `webhook` | — | Récupère les informations de connexion avec le webhook. |
