from pydantic import BaseModel


class SupplierOut(BaseModel):
    siret: str
    raison_sociale: str | None = None
    iban: str | None = None
    adresse: str | None = None
    tva_intracommunautaire: str | None = None
    conformite_status: str | None = None
    documents: list[dict] = []