# Schéma complet des collections MongoDB – Hackathon 2026

Schéma de référence aligné avec **docs/DONNEES.md** (entités BDD, champs, index).  
Base : **MongoDB Atlas** – base de données `hackathon`.

---

## 1. Collection `users`

Utilisateurs de l’application (connexion, propriétaire des documents).

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `_id` | ObjectId | oui | Clé primaire (auto). |
| `email` | string | oui | Unique. |
| `password_hash` | string | oui | Mot de passe hashé. |
| `nom` | string | non | Nom affiché. |
| `created_at` | Date | oui | Date de création. |

**Index :**
- `{ email: 1 }` unique.

---

## 2. Collection `documents`

Un document = un fichier uploadé + métadonnées + résultat d’extraction (IA + validation).

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `_id` | ObjectId | oui | Clé primaire (auto). |
| `user_id` | ObjectId | oui | Référence `users._id`. |
| `nom_fichier_original` | string | oui | Nom du fichier uploadé. |
| `type_mime` | string | non | application/pdf, image/*, etc. |
| `chemin_minio_bronze` | string | non | Chemin MinIO zone Raw. |
| `chemin_minio_silver` | string | non | Dossier Silver (ocr + extraction). |
| `statut_traitement` | string | oui | en_attente, en_cours, termine, erreur. |
| `job_id` | string | non | Référence job Airflow. |
| `type_document_extrait` | string | non | facture, devis, avoir, attestation_siret, etc. |
| `resultat_extraction` | object | non | { type, confidence, donnees, signales }. |
| `texte_ocr` | string | non | Texte OCR brut (optionnel). |
| `created_at` | Date | oui | Création. |
| `updated_at` | Date | oui | Dernière mise à jour. |

**Index :**
- `{ user_id: 1, created_at: -1 }` – liste des documents par utilisateur.
- `{ statut_traitement: 1 }` – filtres par statut.
- `{ user_id: 1, statut_traitement: 1 }` – optionnel.

---

## 3. Exemple de document `documents` (après traitement)

```json
{
  "_id": ObjectId("..."),
  "user_id": ObjectId("..."),
  "nom_fichier_original": "facture-2026-001.pdf",
  "type_mime": "application/pdf",
  "chemin_minio_bronze": "bronze/uploads/user123/batch456/facture-2026-001.pdf",
  "chemin_minio_silver": "silver/processed/user123/doc789/",
  "statut_traitement": "termine",
  "job_id": "document_processing_20260316_001",
  "type_document_extrait": "facture",
  "resultat_extraction": {
    "type": "facture",
    "confidence": 0.95,
    "donnees": {
      "numero_facture": "FAC-001",
      "date_facture": "2026-03-01",
      "fournisseur": { "raison_sociale": "...", "siret": "..." },
      "client": { "raison_sociale": "...", "siret": "..." },
      "montant_ht": 100,
      "montant_ttc": 120
    },
    "signales": []
  },
  "created_at": ISODate("2026-03-16T10:00:00Z"),
  "updated_at": ISODate("2026-03-16T10:05:00Z")
}
```
