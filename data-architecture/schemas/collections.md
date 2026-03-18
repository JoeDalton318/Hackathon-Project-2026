# Schéma complet des collections MongoDB – Hackathon 2026

Schéma de référence **aligné avec le backend FastAPI** (models, services).  
Base : **MongoDB Atlas** – nom de base configuré via `MONGO_DB` (ex. `hackathon`).

---

## 1. Collection `users`

Utilisateurs de l’application (connexion, propriétaire des documents).  
Clé métier : `user_id` (UUID string). Les documents référencent ce `user_id`.

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `_id` | ObjectId | oui | Clé primaire MongoDB (auto). |
| `user_id` | string | oui | UUID, identifiant métier (référencé par `documents.user_id`). |
| `email` | string | oui | Unique. |
| `hashed_password` | string | oui | Mot de passe hashé. |
| `nom` | string | non | Nom affiché. |
| `role` | string | oui | `"user"` ou `"admin"`. |
| `created_at` | Date | oui | Date de création. |

**Index :**
- `{ email: 1 }` unique.

---

## 2. Collection `documents`

Un document = un fichier uploadé + métadonnées + résultat d’extraction (IA + validation).  
Clé métier : `document_id` (UUID string).

| Champ | Type | Obligatoire | Description |
|-------|------|-------------|-------------|
| `_id` | ObjectId | oui | Clé primaire MongoDB (auto). |
| `document_id` | string | oui | UUID, identifiant métier (utilisé par l’API). |
| `user_id` | string | oui | Référence `users.user_id` (UUID). |
| `original_filename` | string | oui | Nom du fichier uploadé. |
| `mime_type` | string | non | application/pdf, image/*, etc. |
| `minio_path` | string | oui | Chemin du fichier dans MinIO (Bronze ou Silver selon convention). |
| `status` | string | oui | `pending`, `processing`, `ocr_done`, `extraction_done`, `done`, `error`. |
| `document_type` | string | non | `facture`, `devis`, `kbis`, `rib`, `attestation_urssaf`, `attestation_siret`, `unknown`. |
| `extracted_data` | object | non | Données structurées extraites par l’IA. |
| `anomalies` | array | non | Liste des anomalies / signales. |
| `created_at` | Date | oui | Création. |
| `updated_at` | Date | oui | Dernière mise à jour. |

**Index :**
- `{ user_id: 1, created_at: 1 }` – liste des documents par utilisateur.
- `{ status: 1 }` – filtres par statut.
- `{ user_id: 1, status: 1 }` – optionnel.

---

## 3. Exemple de document `documents` (après traitement)

```json
{
  "_id": ObjectId("..."),
  "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "u1u2u3u4-u5u6-7890-user-abcdef123456",
  "original_filename": "facture-2026-001.pdf",
  "mime_type": "application/pdf",
  "minio_path": "bronze/uploads/u1u2u3u4/batch456/facture-2026-001.pdf",
  "status": "done",
  "document_type": "facture",
  "extracted_data": {
    "numero_facture": "FAC-001",
    "date_facture": "2026-03-01",
    "fournisseur": { "raison_sociale": "...", "siret": "..." },
    "client": { "raison_sociale": "...", "siret": "..." },
    "montant_ht": 100,
    "montant_ttc": 120
  },
  "anomalies": [],
  "created_at": ISODate("2026-03-16T10:00:00Z"),
  "updated_at": ISODate("2026-03-16T10:05:00Z")
}
```
