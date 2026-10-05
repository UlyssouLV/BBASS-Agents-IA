# Recherche V1.1.3 — usage et tarification de l'API Mistral

Date de la recherche : 2026-09-17

## Périmètre

Recherche documentaire externe (sources primaires uniquement : docs.mistral.ai et mistral.ai) pour préparer la V1.1.3 (suivi de consommation Mistral). Le backend BBASS-Agents-IA appelle aujourd'hui :

- `POST https://api.mistral.ai/v1/chat/completions` (modèle `mistral-small-latest`) — la méthode `chat()` ne garde que `message["content"]`, le reste de la réponse (dont un éventuel `usage`) est jeté.
- `POST https://api.mistral.ai/v1/ocr` (modèle `mistral-ocr-latest`) — la méthode `ocr()` envoie le document en base64 inline et ne garde que le markdown des pages.

Les 4 questions ci-dessous visent à déterminer si un suivi de consommation/coût est possible à partir des réponses des appels existants, et si les prix par modèle sont récupérables par API ou doivent être recopiés en dur.

---

## Question 1 — `POST /v1/chat/completions` renvoie-t-il un `usage` garanti ?

**Verdict : Oui pour les appels non-streamés (champ présent et marqué requis dans le schéma). Partiel/non confirmé pour le streaming — aucune source primaire consultée ne documente explicitement le comportement de `usage` en mode `stream=true`.**

- Source primaire : https://docs.mistral.ai/api/endpoint/chat
  Le schéma de la réponse 200 de `POST /v1/chat/completions` liste `"usage": "*[UsageInfo](#operation-chat_completion_v1_chat_completions_post_responses_200_application-json_usage_usageinfo)"` — l'astérisque marque le champ comme **requis** dans la réponse JSON non-streamée.

- Source primaire (schéma détaillé) : https://docs.mistral.ai/openapi.yaml
  L'objet `UsageInfo` référencé contient (entre autres) :
  - `prompt_tokens` (integer, défaut 0)
  - `completion_tokens` (integer|null, défaut 0)
  - `total_tokens` (integer, défaut 0)
  - `prompt_tokens_details` (objet détaillé, ex. tokens en cache)
  - `completion_tokens_details`
  - `num_cached_tokens`
  - `request_count`
  - `prompt_audio_seconds`

  Ce sont bien des noms équivalents à `prompt_tokens` / `completion_tokens` / `total_tokens` demandés dans la question.

- Streaming, `tool_calls`, `response_format` JSON : je n'ai pas trouvé, sur `docs.mistral.ai/api/endpoint/chat` ni sur `docs.mistral.ai/capabilities/completion/`, de section documentant explicitement le schéma de l'événement SSE streamé (`CompletionEvent`) ni une mention d'un paramètre `stream_options`/`include_usage` (par comparaison, OpenAI documente ce paramètre explicitement pour ce cas). La page `docs.mistral.ai/capabilities/completion/` montre des exemples "Non-Streaming" / "Streaming" mais le contenu affiché ne couvre que le cas non-streamé, et ne mentionne aucune différence de comportement de `usage` selon `tool_calls` ou `response_format`. **Ce point n'a donc pas pu être confirmé par une source primaire** — voir section Limites.

**Conséquence pratique pour la V1.1.3** : en mode non-streamé (ce que fait `chat()` aujourd'hui, a priori — à vérifier dans le code), `usage.total_tokens` (et `prompt_tokens`/`completion_tokens`) devrait être disponible à chaque appel et peut être conservé au lieu d'être jeté. Le comportement en streaming reste à vérifier empiriquement si le code utilise `stream=true`.

---

## Question 2 — `POST /v1/ocr` renvoie-t-il un équivalent (pages traitées, tokens, `usage`) ?

**Verdict : Oui. Un champ `usage_info` (type `OCRUsageInfo`) est présent, avec un compte de pages — pas de compte de tokens.**

- Source primaire : https://docs.mistral.ai/api/endpoint/ocr
  La réponse 200 de `POST /v1/ocr` inclut `usage_info: OCRUsageInfo`, avec un exemple de réponse :
  ```json
  "usage_info": {
    "pages_processed": 29,
    "doc_size_bytes": null
  }
  ```
  Champs exacts : `pages_processed` (integer — nombre de pages traitées, base du coût "$X / 1000 pages") et `doc_size_bytes` (integer|null — taille du document).

  Aucun champ de type "tokens" n'apparaît dans `OCRUsageInfo` : la facturation OCR est basée sur le nombre de pages, cohérent avec la tarification "par 1000 pages" trouvée en Q4.

**Conséquence pratique** : `ocr()` peut conserver `usage_info.pages_processed` (actuellement jeté avec le reste de la réponse) pour calculer un coût, en le multipliant par le prix par page.

---

## Question 3 — Existe-t-il une API de tarification/billing programmable, ou seulement une page humaine ?

**Verdict : Partiel / plutôt Non pour un calcul de coût "au fil de l'eau" par le backend applicatif.**

- `GET /v1/models` et `GET /v1/models/{model_id}` : source primaire https://docs.mistral.ai/api/endpoint/models — le schéma de l'objet modèle (`BaseModelCard`/`FTModelCard`) liste `id`, `capabilities`, `job`, `root`, `object`, `created`, `owned_by`, `max_context_length`, `aliases`, `archived`, etc. **Aucun champ de prix n'est présent.** Donc pas de tarifs récupérables via `/v1/models`.

- Une **Admin API de suivi de consommation existe bien**, mais avec des limites importantes pour ce cas d'usage :
  - Source primaire : https://docs.mistral.ai/admin/billing-usage/usage-limits — renvoie explicitement vers "Usage metrics with the Admin API" pour le reporting programmatique : *« For programmatic usage reporting, see Usage metrics with the Admin API »*. Cette même page renvoie aussi vers la page de tarifs humaine pour les prix courants : *« For current pricing and model availability, see Mistral pricing »* (lien vers `https://mistral.ai/pricing/`).
  - Source primaire : https://docs.mistral.ai/admin/admin-api/usage-metrics — cette Admin API renvoie la consommation **déjà décomposée en coût monétaire** par catégorie (`chat`, `completion`, `ocr`, `audio`, `connectors`, `libraries_api`, `fine_tuning`, `vibe_usage`), avec une période (`start_date`, `end_date`) et une `currency`. Mais : (a) elle nécessite une **clé Admin API créée dans le Backoffice** (accès organisation, pas une clé API applicative standard) — donc pas appelable simplement depuis le backend qui relaie les appels Mistral ; (b) c'est un usage **agrégé par catégorie/période**, pas un tarif "par token" exploitable pour calculer le coût d'un appel individuel en temps réel ; (c) le contenu exact de la réponse JSON (noms de champs précis au-delà des catégories citées) n'a pas pu être confirmé avec une citation verbatim complète — voir Limites.

- **Conclusion pratique** : il n'existe pas d'endpoint public type "tarifs par modèle en JSON" consultable avec une clé API standard. La page humaine https://mistral.ai/pricing/api/ reste, à ma connaissance après cette recherche, le seul moyen de connaître le prix par token/par page et doit être recopiée (et datée) en dur dans le code, avec une revue périodique. L'Admin API de billing existe pour un usage de reporting organisationnel a posteriori, pas pour un calcul de coût par requête intégré au flux `chat()`/`ocr()`.

---

## Question 4 — Tarifs actuels pour `mistral-small-latest` et `mistral-ocr-latest`

**Valeurs figées au 2026-09-17, sans garantie de stabilité — à revérifier avant intégration et à dater dans le code.**

- Source primaire : https://mistral.ai/pricing/api/
  - Ligne « Mistral Small 4 » : *« Input (/M tokens) $0.15 »* et *« Output (/M tokens) $0.6 »* — soit 0,15 $ / million de tokens en entrée et 0,60 $ / million de tokens en sortie.
  - Ligne « OCR 4.1 » : *« OCR $4 / 1000 pages »* (et *« Document AI $5 / 1000 pages »* pour le produit Document AI distinct, à ne pas confondre avec l'OCR simple).

- **Limite de correspondance alias → nom commercial** : la page de tarifs affiche des noms commerciaux (« Mistral Small 4 », « OCR 4.1 ») et non les identifiants d'API exacts `mistral-small-latest` / `mistral-ocr-latest`. Je n'ai pas trouvé, sur une page `docs.mistral.ai` consultée, de phrase confirmant explicitement et verbatim que l'alias `mistral-small-latest` pointe aujourd'hui vers « Mistral Small 4 » et que `mistral-ocr-latest` pointe vers « OCR 4.1 » (recherche sur `docs.mistral.ai/models/overview`, page consultée mais sans le passage explicite). Une recherche web (non primaire, donc non citable comme preuve) suggère que c'est bien le cas actuellement, mais ce point precis reste à confirmer par une source primaire avant de figer ces prix dans le code — voir Limites.

---

## Limites / ce qui reste à vérifier

1. **Comportement de `usage` en streaming** (`stream=true`) sur `POST /v1/chat/completions` : non confirmé par une source primaire. À tester empiriquement (ou à chercher dans le schéma complet `CompletionEvent` de l'OpenAPI, que je n'ai pas réussi à faire restituer intégralement via l'outil de récupération web) avant de compter dessus si `chat()` utilise ou pourrait utiliser le streaming.
2. **Comportement de `usage` avec `tool_calls` ou `response_format` JSON** : aucune mention trouvée d'une différence de comportement ; présumé identique (champ requis) au cas de base, mais non confirmé explicitement par une phrase de la documentation dédiée à ce cas.
3. **Contenu exact (noms de champs complets) de la réponse de l'Admin API `usage-metrics`** au-delà des catégories citées (`chat`, `completion`, `ocr`, etc.) et de `start_date`/`end_date`/`currency` : je n'ai pas pu récupérer un exemple JSON complet verbatim malgré plusieurs tentatives — la page a été consultée mais le contenu retourné par l'outil de récupération était partiel.
4. **Correspondance exacte alias → modèle commercial** (`mistral-small-latest` → « Mistral Small 4 », `mistral-ocr-latest` → « OCR 4.1 ») : non confirmée par une citation primaire verbatim malgré la recherche sur `docs.mistral.ai/models/overview` et `docs.mistral.ai/models`. À reconfirmer avant d'utiliser ces prix comme référence figée en dur, par exemple en appelant `GET /v1/models/mistral-small-latest` et `GET /v1/models/mistral-ocr-latest` (champ `root` ou `aliases`) sur un environnement de test.
5. Les prix cités en Q4 sont une **photographie au 2026-09-17** de https://mistral.ai/pricing/api/, page qui peut changer sans préavis ; aucune clause de stabilité n'a été trouvée sur la page elle-même lors de cette recherche.
