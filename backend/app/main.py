"""
FastAPI Backend - Point d'entrée
À personnaliser par l'équipe backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Hackathon Data Engineering API",
    description="API pour l'upload de documents et l'interface avec la BDD",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À adapter en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Endpoint de santé"""
    return {"status": "ok", "message": "API Hackathon is running"}

@app.get("/health")
async def health_check():
    """Vérification de l'état de l'API"""
    return {"status": "healthy"}

# TODO: Ajouter vos endpoints ici
# - Upload de documents
# - Récupération des données
# - etc.
