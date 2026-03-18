#!/usr/bin/env python3
"""
Script d'initialisation MongoDB – Hackathon 2026 (Data Architecture).
- Vérifie la connexion à la base.
- Crée les collections users et documents si elles n'existent pas.
- Crée les index définis dans schemas/collections.md.

Usage :
  cd data-architecture/scripts && pip install -r requirements.txt
  export MONGO_URL="mongodb+srv://user:password@cluster.mongodb.net/?appName=..."
  python init_mongodb.py

Ou avec un .env à la racine de data-architecture/ contenant MONGO_URL.
"""

import os
import sys

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure
except ImportError:
    print("Erreur: installez les dépendances avec pip install -r requirements.txt")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Charger .env depuis data-architecture/ ou le répertoire courant
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
if load_dotenv:
    load_dotenv(os.path.join(PARENT_DIR, ".env"))
    load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

DB_NAME = os.environ.get("MONGO_DB", "hackathon")
COLLECTION_USERS = "users"
COLLECTION_DOCUMENTS = "documents"


def get_mongo_url() -> str:
    url = os.environ.get("MONGO_URL", "").strip()
    if not url:
        print("Erreur: variable d'environnement MONGO_URL non définie.")
        print("Définissez MONGO_URL ou créez un fichier .env (voir .env.example).")
        sys.exit(1)
    return url


def check_connection(client: MongoClient) -> bool:
    """Vérifie que la base est bien connectée."""
    try:
        client.admin.command("ping")
        return True
    except ConnectionFailure:
        return False


def create_collections(db):
    """Crée les collections si elles n'existent pas."""
    existing = db.list_collection_names()
    if COLLECTION_USERS not in existing:
        db.create_collection(COLLECTION_USERS)
        print(f"  Collection '{COLLECTION_USERS}' créée.")
    else:
        print(f"  Collection '{COLLECTION_USERS}' existe déjà.")
    if COLLECTION_DOCUMENTS not in existing:
        db.create_collection(COLLECTION_DOCUMENTS)
        print(f"  Collection '{COLLECTION_DOCUMENTS}' créée.")
    else:
        print(f"  Collection '{COLLECTION_DOCUMENTS}' existe déjà.")


def create_indexes(db):
    """Crée les index selon schemas/collections.md."""
    # users: email unique
    db[COLLECTION_USERS].create_index([("email", 1)], unique=True)
    print("  Index users: email (unique) créé ou déjà présent.")

    # documents: user_id + created_at, status, user_id + status (aligné backend)
    db[COLLECTION_DOCUMENTS].create_index([("user_id", 1), ("created_at", 1)])
    db[COLLECTION_DOCUMENTS].create_index([("status", 1)])
    db[COLLECTION_DOCUMENTS].create_index([("user_id", 1), ("status", 1)])
    print("  Index documents: user_id+created_at, status, user_id+status créés ou déjà présents.")


def main():
    print("Initialisation MongoDB – Hackathon 2026")
    print("-" * 40)

    mongo_url = get_mongo_url()
    # Masquer le mot de passe dans les logs
    safe_url = mongo_url.split("@")[-1] if "@" in mongo_url else mongo_url[:50]
    print(f"Connexion à: ...@{safe_url}")

    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    except Exception as e:
        print(f"Erreur de connexion: {e}")
        sys.exit(1)

    if not check_connection(client):
        print("Erreur: impossible de contacter le serveur MongoDB (ping). Vérifiez MONGO_URL et l'accès réseau.")
        sys.exit(1)
    print("Connexion vérifiée (ping OK).")

    db = client[DB_NAME]
    print(f"\nBase de données: '{DB_NAME}'")

    print("\nCréation des collections (si nécessaire)...")
    create_collections(db)

    print("\nCréation des index...")
    create_indexes(db)

    print("\nInitialisation terminée avec succès.")
    client.close()


if __name__ == "__main__":
    main()
