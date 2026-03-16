-- Script d'initialisation de la base de données PostgreSQL
-- À personnaliser par l'équipe backend/data

-- Création d'une table exemple (à adapter selon vos besoins)
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50),
    metadata JSONB
);

-- Création d'index pour les performances
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_upload_date ON documents(upload_date);

-- TODO: Ajouter vos propres tables et schémas ici
