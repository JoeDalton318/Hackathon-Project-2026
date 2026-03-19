from pydantic import BaseModel


class SupplierOut(BaseModel):
    siret: str
    supplier_name: str | None = None
    iban: str | None = None
    address: str | None = None
    tva_number: str | None = None
    decision: str | None = None
    documents: list[dict] = []
