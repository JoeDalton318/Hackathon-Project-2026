# Validation Engine

Module de validation intelligente.

## Objectif

Cette brique intervient après l'OCR et l'extraction des champs structurés.  
Elle permet de contrôler la conformité et la cohérence de documents administratifs/comptables, puis de produire une décision exploitable par le backend et le frontend :

- `approved`
- `review`
- `blocked`

---

## Principaux contrôles implémentés

### Contrôles unitaires
Le moteur vérifie notamment :
- le format des identifiants (`SIRET`, `SIREN`, `TVA`)
- la validité de `IBAN` / `BIC`
- la cohérence des montants (`HT`, `TVA`, `TTC`)
- la cohérence des dates
- les champs obligatoires
- les documents trop incomplets
- la faible confiance OCR sur les champs critiques

### Contrôles inter-documents
Le moteur compare plusieurs documents d’un même batch pour détecter :
- une incohérence de `SIRET`
- une incohérence `facture` vs `attestation`
- une incohérence `facture` vs `RIB`
- des doublons de facture
- des incohérences de nom fournisseur

### Détection d’anomalies ML
Le moteur inclut un modèle complémentaire basé sur `IsolationForest`.

---
## Exemple Fonctionnement du process

### Vue d’ensemble

1. l’utilisateur se connecte et upload un ou plusieurs documents depuis le frontend
2. On stocke chaque fichier brut dans MinIO (`raw`) et crée un `document_id` pour chaque document
3. tous les documents d’un même utilisateur / même lot d’upload doivent conserver un identifiant commun de regroupement (`batch_id` ou équivalent)
4. Airflow lance l’OCR et l’extraction sur chaque document
5. l’OCR / extraction produit un JSON structuré par document
6. avant la validation, les JSON appartenant au même utilisateur / même lot doivent être regroupés dans un même `batch`
7. le module de validation lit ce batch via `main.py`
8. le moteur exécute les contrôles unitaires et inter-documents
9. le résultat batch complet est sauvegardé dans `curated`

### la validation par batch

certaines validations nécessitent plusieurs documents ensemble :
- facture vs attestation
- facture vs RIB
- incohérence de SIRET dans un dossier
- doublon de facture

C’est pourquoi le moteur reçoit un batch de documents.

---
## Entrée attendue

Le moteur attend un objet `BatchInput`, c’est à dire un batch de documents déjà extraits et structurés.

### Format logique attendu

> ⚠️ Exemple de structure.  
> Le format exact pourra être ajusté selon la sortie finale OCR / extraction.

```json

{
  "batch_id": "batch_001",
  "documents": [
    {
      "document_id": "doc_fact_001",
      "doc_type": "facture",
      "fields": {
        "numero_facture": "FAC-2026-001",
        "date_facture": "2026-03-10",
        "date_echeance": "2026-03-25",
        "fournisseur": {
          "raison_sociale": "ACME SARL",
          "siret": "73282932000074",
          "tva_intracommunautaire": "FR23732829320"
        },
        "client": {
          "raison_sociale": "CLIENT XYZ",
          "siret": "42385519600014"
        },
        "amount_ht": 1000.0,
        "amount_tva": 200.0,
        "amount_ttc": 1200.0,
        "confidence": 0.92
      },
      "metadata": {
        "field_confidence": {
          "numero_facture": 0.91,
          "date_facture": 0.89,
          "siret": 0.83
        }
      }
    }
  ]
}
```
---

## Sortie produite

⚠️ Exemple de sortie.  
> Le contenu exact peut évoluer selon les besoins d’intégration backend / frontend.

fichier batch complet dans `curated`

par exemple :

```text
curated/batch_001_validation_result.json
```

```json

{
  "batch_id": "batch_001",
  "status": "completed",
  "validated_at": "2026-03-17T12:00:00",
  "engine_version": "1.1.0",
  "global_score": 240,
  "decision": "blocked",
  "alerts": [
    {
      "rule_code": "TVA_INVALID",
      "severity": "high",
      "message": "Le numéro de TVA est invalide ou incohérent avec le SIREN.",
      "documents": [
        "doc_fact_001"
      ],
      "details": {
        "tva_number": "FR99732829320",
        "siren": "732829320"
      }
    },
  ],
  "signals": [
    {
      "code": "TVA_INCOHERENTE",
      "message": "Le numéro de TVA est invalide ou incohérent avec le SIREN.",
      "champ": null,
      "valeur": "FR99732829320",
      "document_id": "doc_fact_001"
    },
    ],
  "summary": {
    "critical": 0,
    "high": 7,
    "medium": 3,
    "low": 7
  },
  "batch_stats": {
    "documents_total": 4,
    "documents_with_alerts": 4,
    "groups_total": 3
  },
  "blocking_reasons": [
    "DATE_EXPIRATION_DEPASSEE",
    "DOCUMENT_TOO_INCOMPLETE",
    "IBAN_INVALID",
    "SIRET_INVALID",
    "TVA_INVALID",
    "VAT_NEGATIVE_AMOUNT",
    "VAT_TTC_LT_HT"
  ]
}

```

### Ce fichier contient :

- `decision`
- `global_score`
- `alerts`
- `signals`
- `summary`
- `batch_stats`
- `blocking_reasons`


---

## Fichiers principaux

### `main.py`
Point d’entrée d’intégration.
Il :
- lit le JSON d’entrée
- construit le `BatchInput`
- lance le moteur de validation
- écrit le résultat batch dans `curated`

### `app/models.py`
Définit les schémas Pydantic utilisés par le moteur :
- `BatchInput`
- `DocumentInput`
- `DocumentFields`
- `Alert`
- `Signal`
- `ValidationResult`

### `app/validation_core.py`
Contient les fonctions utilitaires :
- normalisation des textes
- parsing des dates
- validation de formats
- similarité
- regroupement documentaire

### `app/validation_rules.py`
Contient l’ensemble des règles métier unitaires et inter-documents.

### `app/validation_engine.py`
Orchestre la validation :
- exécution des règles
- fusion des alertes
- calcul du score
- décision finale
- construction des signaux
- construction des `blocking_reasons`

### `app/insee_client.py`
Gère la vérification des SIRET via l’API SIRENE / INSEE avec fallback mock.

### `app/anomaly_model.py`
Gère le modèle `IsolationForest` :
- extraction de features
- entraînement
- chargement
- détection d’anomalies

### `tests/fixtures/`
Jeux de tests JSON :
- batch valide
- batch invalide
- cas API SIRENE indisponible

### `tests/prepare_ml_data.py`
Génère des données synthétiques pour entraîner le modèle ML.

### `tests/run_all.py`
Exécute les scénarios de test fournis (`valid`, `invalid`, `api unavailable`) et génère les résultats de validation dans `curated`.