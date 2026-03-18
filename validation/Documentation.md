# Validation Engine

Module de validation intelligente.

## Objectif

Elle consomme les extraction.json déposés dans MinIO, applique des règles de validation métier et produit des résultats exploitables par le 
backend et le front.

Le moteur produit deux niveaux de sortie :

- un résultat batch

- un résultat par document

---

## Position dans le workflow global

- upload des documents bruts

- stockage des originaux dans MinIO raw

- OCR / extraction 

- stockage des JSON OCR dans curated/.../extraction.json

- lecture de ces JSON par le moteur de validation

- validation unitaire et inter-documents

- stockage des résultats dans MinIO sous curated/validation/...

curated/validation/batches/YYYY/MM/DD/<batch_id>/validation_result.json
curated/validation/documents/YYYY/MM/DD/<document_id>/validation_result.json

---

# Entrée 

Le moteur lit les résultats OCR structurés depuis MinIO.

## Convention d’entrée lue par la validation


curated/YYYY/MM/DD/<document_id>/extraction.json


Chaque `extraction.json` contient notamment :

- document_id  
- file_name  
- classification  
- ocr_metadata  
- raw_text  
- bloc typé (facture, rib, attestation_urssaf, etc.)

Le module transforme ces JSON OCR en objets internes :

- `DocumentInput`  
- `BatchInput`  

---

# Logique de traitement


Le moteur traite toujours un **batch** :

- si 1 document arrive → batch de 1 document  
- si N documents arrivent ensemble → batch de N documents  

Cela permet d’avoir une seule logique pour :

- les contrôles documentaires unitaires  
- les contrôles inter-documents  

---

# Contrôles implémentés

## Contrôles unitaires

- champs obligatoires  
- document trop incomplet  
- format SIRET / SIREN / TVA  
- format IBAN / BIC  
- cohérence des montants HT / TVA / TTC  
- cohérence des dates  
- attestation expirée  
- attestation trop ancienne  
- faible confiance sur champs critiques  
- suspicion de mauvais type documentaire (`DOCUMENT_TYPE_SUSPECT`)  

---

## Contrôles inter-documents

- incohérence de SIRET dans un groupe  
- incohérence facture / attestation  
- incohérence facture / RIB  
- incohérence de nom fournisseur  
- suspicion de doublon de facture  

---

## Contrôle externe

- vérification avec l'API INSEE / SIRENE 

---

## Contrôle ML

- modèle `IsolationForest` 

---

# Sorties produites

Le moteur produit :

## 1. Résultat batch

Un JSON global de validation :


curated/validation/batches/YYYY/MM/DD/<batch_id>/validation_result.json


## 2. Résultat par document

Un JSON par document :


curated/validation/documents/YYYY/MM/DD/<document_id>/validation_result.json


---

# Structure du résultat batch

Le résultat batch contient notamment :

- batch_id  
- status  
- validated_at  
- engine_version  
- global_score  
- decision  
- alerts  
- signals  
- summary  
- batch_stats  
- blocking_reasons  

---

# Structure du résultat document

Chaque résultat document contient notamment :

- document_id  
- batch_id  
- validated_at  
- engine_version  
- document_type  
- predicted_document_type  
- suspected_document_type  
- decision  
- alerts  
- signals  
- summary  
- extracted_data  
- source  

Le champ `source.source_extraction_key` permet de relier un résultat de validation au `extraction.json` d’origine.

---

# Décisions métier

Le moteur renvoie :

- `approved`  
- `review`  
- `blocked`  

## Interprétation

- **approved** : aucune anomalie bloquante  
- **review** : document à revoir humainement  
- **blocked** : anomalie bloquante ou risque fort  

---

# Fichiers principaux

## main.py

Point d’entrée CLI.

Il :

- lit les JSON OCR depuis MinIO 
- construit le `BatchInput`  
- lance la validation  
- produit les résultats batch + document  
- stocke les résultats dans MinIO `--store-minio`  

---

## app/ocr_adapter.py

Transforme les `extraction.json` OCR en objets internes `DocumentInput`.

---

## app/minio_io.py

Centralise :

- lecture des JSON OCR dans MinIO  
- écriture des résultats de validation dans MinIO  

---

## app/models.py

Schémas Pydantic :

- `BatchInput`  
- `DocumentInput`  
- `DocumentFields`  
- `Alert`  
- `Signal`  
- `ValidationResult`  

---

## app/validation_core.py

Fonctions utilitaires :

- normalisation  
- parsing  
- checksum  
- regroupement documentaire  
- similarité  

---

## app/validation_rules.py

Règles métier unitaires et inter-documents.

---

## app/validation_engine.py

Orchestrateur de validation.

---

## app/result_formatter.py

Construit les résultats documentaires à partir du résultat batch.

---

## app/insee_client.py

Accès à l’API INSEE / SIRENE.

---

## app/anomaly_model.py

Gestion du modèle ML :

entraînement

sauvegarde / chargement

analyse d’anomalies
---

## app/prepare_ml_data.py

Prépare des données pour entraîner le modèle ML de validation.

---

## app/settings.py

Centralise la lecture des variables d’environnement.

---

## Structure du dossier

validation/
├── app/
│   ├── anomaly_model.py        Modèle ML d’anomalie (entraînement, chargement, scoring)
│   ├── insee_client.py         Client API INSEE / SIRENE pour les vérifications externes
│   ├── minio_io.py             Lecture des extraction.json et écriture des résultats dans MinIO
│   ├── models.py               Modèles Pydantic internes (BatchInput, DocumentInput, Alert, etc.)
│   ├── ocr_adapter.py          Transformation des JSON OCR en objets internes de validation
│   ├── prepare_ml_data.py      Génération des données d’entraînement et entraînement du modèle ML
│   ├── result_formatter.py     Construction des résultats finaux par document à partir du batch
│   ├── service.py              Point d’entrée Python réutilisable pour lancer la validation
│   ├── settings.py             Lecture centralisée des variables d’environnement
│   ├── validation_core.py      Fonctions utilitaires : parsing, normalisation, checksum, regroupement
│   ├── validation_engine.py    Orchestrateur principal du moteur de validation
│   ├── validation_rules.py     Règles métier unitaires et inter-documents
│   ├── __init__.py             Exposition des fonctions publiques du module
├── tests/
│   ├── fixtures/
│   │   ├── valid_batch.json            Jeu de test batch valide
│   │   ├── invalid_batch.json          Jeu de test batch invalide
│   │   └── api_unavailable_batch.json  Jeu de test avec API externe indisponible
│   └── run_all.py              Script de lancement des tests fonctionnels
├── .env_example                Exemple de configuration attendue
├── Dockerfile                  Image Docker du module validation
├── Documentation.md            Documentation du module
├── main.py                     Point d’entrée CLI
└── requirements.txt            Dépendances Python

# Tests

## 1. Tests fonctionnels

Les scénarios de test sont dans :

tests/fixtures/


### Fichiers disponibles :

- `valid_batch.json`  
- `invalid_batch.json`  
- `api_unavailable_batch.json`  

Le script :

```bash
tests/run_all.py
```

permet d’exécuter tous les scénarios.

### Lancer les tests

```bash
python tests/run_all.py
```
**Ce script :**

charge les fixtures JSON

construit les BatchInput

lance la validation

affiche les résultats

permet de vérifier rapidement les décisions et alertes attendues

---
## 2. Test du moteur sur MinIO 

**Pré-requis :**

MinIO démarré

des extraction.json présents dans :

curated/.../.../.../extraction.json

Lancer :

```bash
python main.py
```
---

## Intégration avec le reste du système

Le module de validation est conçu pour être découplé et s’intégrer facilement avec :

- le pipeline d’orchestration (**Airflow**)
- le backend API
- **MinIO** comme stockage central

---

## Intégration avec l’OCR

Le moteur de validation dépend uniquement des fichiers produits par l’OCR.

###  Contrat attendu

Les fichiers OCR doivent être déposés dans MinIO sous la forme :
curated/YYYY/MM/DD/<document_id>/extraction.json


### Contenu minimal attendu :

- `document_id`
- `file_name`
- `classification.document_type`
- `ocr_metadata`
- `raw_text`
- bloc structuré selon le type (facture, rib, etc.)


---

## Intégration avec Airflow

Le module de validation peut être exécuté comme une étape du pipeline.

###  Mode d’exécution recommandé

**Via CLI :**

```bash
python main.py --source minio --extraction-key <minio_key>
```
**Via appel Python :**

```bash
from app.service import run_validation
```
run_validation(
    source="minio",
    extraction_keys=[...],
    store_minio=True
)

## Fonctionnement

Airflow récupère un document_id

L’OCR produit extraction.json dans MinIO

Airflow déclenche la validation

**La validation :**

lit depuis MinIO

exécute les règles

écrit les résultats dans MinIO

## Intégration avec le Backend

Le backend consomme les données stockées dans MinIO apres validation.

**Lecture côté backend**

Le backend peut :

lire les résultats de validation via MinIO :

curated/validation/documents/.../validation_result.json



