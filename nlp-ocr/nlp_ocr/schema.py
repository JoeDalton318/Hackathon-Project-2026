"""
nlp_ocr/schema.py
══════════════════
Modèles de données Pydantic.

Principe clé : chaque champ extrait est un ExtractedField qui expose
  value, confidence (0–1), method et raw_ocr.
Jamais de valeur sans métadonnée d'extraction.
"""
from __future__ import annotations
import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    FACTURE              = "facture"
    DEVIS                = "devis"
    ATTESTATION_SIRET    = "attestation_siret"
    ATTESTATION_URSSAF   = "attestation_vigilance_urssaf"
    KBIS                 = "extrait_kbis"
    RIB                  = "rib"
    INCONNU              = "inconnu"


class ExtractionMethod(str, Enum):
    REGEX        = "regex_pattern"
    NER_MODEL    = "ner_model"
    RULE_BASED   = "rule_based"
    NOT_FOUND    = "not_found"


class ExtractedField(BaseModel):
    value:      Optional[str]    = None
    confidence: float            = Field(default=0.0, ge=0.0, le=1.0)
    method:     ExtractionMethod = ExtractionMethod.NOT_FOUND
    raw_ocr:    Optional[str]    = None

    def is_reliable(self, threshold: float = 0.75) -> bool:
        return self.confidence >= threshold and self.value is not None

    @classmethod
    def found(cls, value: str, confidence: float,
              method: ExtractionMethod, raw_ocr: Optional[str] = None) -> "ExtractedField":
        return cls(value=value, confidence=confidence, method=method, raw_ocr=raw_ocr)


class OcrMetadata(BaseModel):
    engine_primary:      str       = "tesseract"
    engine_used:         str       = "tesseract"
    fallback_triggered:  bool      = False
    ocr_confidence_avg:  float     = 0.0
    page_count:          int       = 1
    preprocessing_steps: list[str] = Field(default_factory=list)
    processing_time_ms:  float     = 0.0
    raw_text_length:     int       = 0


class ClassificationResult(BaseModel):
    document_type: DocumentType
    confidence:    float             = Field(ge=0.0, le=1.0)
    scores:        dict[str, float]  = Field(default_factory=dict)


class EntrepriseInfo(BaseModel):
    nom:          ExtractedField = Field(default_factory=ExtractedField)
    siret:        ExtractedField = Field(default_factory=ExtractedField)
    siren:        ExtractedField = Field(default_factory=ExtractedField)
    tva_intracom: ExtractedField = Field(default_factory=ExtractedField)
    adresse:      ExtractedField = Field(default_factory=ExtractedField)
    code_postal:  ExtractedField = Field(default_factory=ExtractedField)
    ville:        ExtractedField = Field(default_factory=ExtractedField)
    telephone:    ExtractedField = Field(default_factory=ExtractedField)
    email:        ExtractedField = Field(default_factory=ExtractedField)
    iban:         ExtractedField = Field(default_factory=ExtractedField)
    bic:          ExtractedField = Field(default_factory=ExtractedField)


class FactureData(BaseModel):
    numero_facture: ExtractedField = Field(default_factory=ExtractedField)
    date_emission:  ExtractedField = Field(default_factory=ExtractedField)
    date_echeance:  ExtractedField = Field(default_factory=ExtractedField)
    montant_ht:     ExtractedField = Field(default_factory=ExtractedField)
    montant_tva:    ExtractedField = Field(default_factory=ExtractedField)
    taux_tva:       ExtractedField = Field(default_factory=ExtractedField)
    montant_ttc:    ExtractedField = Field(default_factory=ExtractedField)
    emetteur:       EntrepriseInfo = Field(default_factory=EntrepriseInfo)
    destinataire:   EntrepriseInfo = Field(default_factory=EntrepriseInfo)
    objet:          ExtractedField = Field(default_factory=ExtractedField)


class DevisData(BaseModel):
    numero_devis:  ExtractedField = Field(default_factory=ExtractedField)
    date_emission: ExtractedField = Field(default_factory=ExtractedField)
    date_validite: ExtractedField = Field(default_factory=ExtractedField)
    montant_ht:    ExtractedField = Field(default_factory=ExtractedField)
    montant_ttc:   ExtractedField = Field(default_factory=ExtractedField)
    emetteur:      EntrepriseInfo = Field(default_factory=EntrepriseInfo)
    client:        EntrepriseInfo = Field(default_factory=EntrepriseInfo)


class AttestationSiretData(BaseModel):
    denomination:  ExtractedField = Field(default_factory=ExtractedField)
    siret:         ExtractedField = Field(default_factory=ExtractedField)
    siren:         ExtractedField = Field(default_factory=ExtractedField)
    activite:      ExtractedField = Field(default_factory=ExtractedField)
    date_creation: ExtractedField = Field(default_factory=ExtractedField)
    adresse:       ExtractedField = Field(default_factory=ExtractedField)


class AttestationUrssafData(BaseModel):
    denomination:       ExtractedField = Field(default_factory=ExtractedField)
    siret:              ExtractedField = Field(default_factory=ExtractedField)
    date_emission:      ExtractedField = Field(default_factory=ExtractedField)
    date_expiration:    ExtractedField = Field(default_factory=ExtractedField)
    numero_attestation: ExtractedField = Field(default_factory=ExtractedField)
    is_expired:         Optional[bool] = None


class KbisData(BaseModel):
    denomination:         ExtractedField = Field(default_factory=ExtractedField)
    siren:                ExtractedField = Field(default_factory=ExtractedField)
    forme_juridique:      ExtractedField = Field(default_factory=ExtractedField)
    capital_social:       ExtractedField = Field(default_factory=ExtractedField)
    date_immatriculation: ExtractedField = Field(default_factory=ExtractedField)
    adresse_siege:        ExtractedField = Field(default_factory=ExtractedField)
    dirigeants:           list[str]      = Field(default_factory=list)


class RibData(BaseModel):
    titulaire: EntrepriseInfo = Field(default_factory=EntrepriseInfo)
    banque:    ExtractedField = Field(default_factory=ExtractedField)
    iban:      ExtractedField = Field(default_factory=ExtractedField)
    bic:       ExtractedField = Field(default_factory=ExtractedField)


class ExtractionResult(BaseModel):
    document_id:    str
    file_name:      str
    classification: ClassificationResult
    ocr_metadata:   OcrMetadata
    raw_text:       str = ""

    facture:            Optional[FactureData]           = None
    devis:              Optional[DevisData]             = None
    attestation_siret:  Optional[AttestationSiretData]  = None
    attestation_urssaf: Optional[AttestationUrssafData] = None
    kbis:               Optional[KbisData]              = None
    rib:                Optional[RibData]               = None

    overall_confidence:  float     = 0.0
    fields_extracted:    int       = 0
    fields_reliable:     int       = 0
    extraction_warnings: list[str] = Field(default_factory=list)
    created_at:          str       = Field(
<<<<<<< HEAD
        default_factory=lambda: datetime.datetime.utcnow().isoformat()
=======
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
>>>>>>> origin/maria
    )

    def get_typed_data(self):
        return {
            DocumentType.FACTURE:            self.facture,
            DocumentType.DEVIS:              self.devis,
            DocumentType.ATTESTATION_SIRET:  self.attestation_siret,
            DocumentType.ATTESTATION_URSSAF: self.attestation_urssaf,
            DocumentType.KBIS:               self.kbis,
            DocumentType.RIB:                self.rib,
        }.get(self.classification.document_type)
