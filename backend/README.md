# Backend Test — Aligné Data-architecture

Copie du backend avec **toutes les modifications** pour être aligné sur la data-architecture (Hackathon-Project-2026/data-architecture).

## Différences avec `backend/`

| Zone | Backend original | Backend_test (data-arch) |
|------|------------------|---------------------------|
| **Documents** | Pas de `user_id`, un seul `minio_path`, `status` (PENDING, DONE…), `extracted_data` / `anomalies` | `user_id` obligatoire, `chemin_minio_bronze` + `chemin_minio_silver`, `statut_traitement` (en_attente, en_cours, termine, erreur), `resultat_extraction` (type, confidence, donnees, signales) |
| **Users** | `hashed_password` | `password_hash` (nom data-arch) |
| **MinIO** | Chemin `{document_id}/{filename}` | Bronze: `bronze/uploads/{user_id}/{batch_id}/{filename}` |
| **Auth documents** | Routes documents sans auth | Toutes les routes documents exigent `get_current_user`, filtrage par `user_id` |
| **Index MongoDB** | Aucun | Index créés au démarrage: users (email unique), documents (user_id+created_at, statut_traitement, user_id+statut_traitement) |
| **Démarrage** | `init_buckets()` commenté | `create_indexes()` + `init_buckets()` appelés dans le lifespan |

## Lancer

Depuis la racine du repo (ou depuis `backend_test` avec `PYTHONPATH=.`):

```bash
cd backend_test
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Variables d’environnement: même `.env` que le backend (MONGO_URL, MINIO_*, AIRFLOW_*, JWT_*, etc.).
