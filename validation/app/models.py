from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high", "critical"]
Decision = Literal["approved", "review", "blocked"]


class Party(BaseModel):
    raison_sociale: Optional[str] = None
    siret: Optional[str] = None
    siren: Optional[str] = None
    tva_intracommunautaire: Optional[str] = None
    adresse: Optional[Any] = None
    email: Optional[str] = None
    telephone: Optional[str] = None


class LineItem(BaseModel):
    designation: Optional[str] = None
    quantite: Optional[float] = None
    pu_ht: Optional[float] = None
    montant_ht: Optional[float] = None


class DocumentFields(BaseModel):
    supplier_name: Optional[str] = None
    siret: Optional[str] = None
    siren: Optional[str] = None
    tva_number: Optional[str] = None

    invoice_date: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None

    amount_ht: Optional[float] = None
    amount_tva: Optional[float] = None
    amount_ttc: Optional[float] = None

    iban: Optional[str] = None
    bic: Optional[str] = None

    numero_facture: Optional[str] = None
    date_facture: Optional[str] = None
    date_echeance: Optional[str] = None

    numero_devis: Optional[str] = None
    date_devis: Optional[str] = None
    date_validite: Optional[str] = None

    numero_avoir: Optional[str] = None
    date_avoir: Optional[str] = None
    reference_facture_origine: Optional[str] = None

    numero_commande: Optional[str] = None
    date_commande: Optional[str] = None

    date_livraison: Optional[str] = None
    reference_commande: Optional[str] = None

    date_debut: Optional[str] = None
    date_fin: Optional[str] = None

    date_debut_periode: Optional[str] = None
    date_fin_periode: Optional[str] = None

    date_emission: Optional[str] = None
    date_expiration: Optional[str] = None

    siret_siege: Optional[str] = None
    siret_ou_siren: Optional[str] = None
    denomination: Optional[str] = None

    titulaire: Optional[str] = None
    banque: Optional[str] = None
    devise: Optional[str] = None
    taux_tva: Optional[Any] = None
    type_tva: Optional[str] = None
    confidence: Optional[float] = None

    fournisseur: Optional[Party] = None
    client: Optional[Party] = None
    emetteur: Optional[Party] = None
    destinataire: Optional[Party] = None
    commanditaire: Optional[Party] = None
    titulaire_compte: Optional[Party] = None
    partie_1: Optional[Party] = None
    partie_2: Optional[Party] = None

    lignes: Optional[List[LineItem]] = None


class DocumentInput(BaseModel):
    document_id: str
    doc_type: str
    fields: DocumentFields
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BatchInput(BaseModel):
    batch_id: str
    documents: List[DocumentInput]


class Alert(BaseModel):
    rule_code: str
    severity: Severity
    message: str
    documents: List[str]
    details: Dict[str, Any] = Field(default_factory=dict)


class Signal(BaseModel):
    code: str
    message: str
    champ: Optional[str] = None
    valeur: Optional[Any] = None
    document_id: Optional[str] = None


class ValidationSummary(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class BatchStats(BaseModel):
    documents_total: int = 0
    documents_with_alerts: int = 0
    groups_total: int = 0


class ValidationResult(BaseModel):
    batch_id: str
    status: str
    validated_at: str
    engine_version: str
    global_score: int
    decision: Decision
    alerts: List[Alert]
    signals: List[Signal] = Field(default_factory=list)
    summary: ValidationSummary
    batch_stats: BatchStats
    blocking_reasons: List[str] = Field(default_factory=list)