/**
 * Script de création des index MongoDB – Hackathon 2026
 * À exécuter avec mongosh après connexion au cluster Atlas :
 *   mongosh "<MONGO_URL>" --file init-scripts/02-mongodb-indexes.js
 * Ou depuis mongosh : load("02-mongodb-indexes.js")
 */

db = db.getSiblingDB("hackathon");

// --- users ---
db.users.createIndex({ email: 1 }, { unique: true });

// --- documents (aligné backend) ---
db.documents.createIndex({ user_id: 1, created_at: 1 });
db.documents.createIndex({ status: 1 });
db.documents.createIndex({ user_id: 1, status: 1 });

print("Index créés avec succès.");
