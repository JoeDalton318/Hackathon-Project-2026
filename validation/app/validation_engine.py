from typing import List, Optional
from datetime import datetime
from .validation_core import build_document_groups
from .anomaly_model import DocumentAnomalyModel
from .insee_client import InseeClient
from .models import Alert, BatchInput, BatchStats, Signal, ValidationResult, ValidationSummary
from .validation_rules import (
    rule_amount_consistency,
    rule_attestation_expired,
    rule_attestation_too_old,
    rule_date_consistency,
    rule_duplicate_invoices,
    rule_facture_attestation_siret_mismatch,
    rule_fraud_heuristics,
    rule_invoice_rib_mismatch,
    rule_low_confidence_critical_fields,
    rule_missing_required_fields,
    rule_nonstandard_vat_rate,
    rule_reference_format,
    rule_rib_format,
    rule_siren_format,
    rule_siret_format,
    rule_siret_mismatch_across_documents,
    rule_supplier_name_mismatch,
    rule_siret_exists_insee_batch,
    rule_tva_consistency,
    rule_vat_business_logic,
    rule_document_too_incomplete,
)
SEVERITY_SCORES = {
    "critical": 40,
    "high": 25,
    "medium": 10,
    "low": 5,
}

RULE_TO_SIGNAL_CODE = {
    "SIRET_INVALID": "SIRET_INVALIDE_FORMAT",
    "SIREN_INVALID": "SIREN_INVALIDE_FORMAT",
    "TVA_INVALID": "TVA_INCOHERENTE",
    "VAT_AMOUNT_MISMATCH": "MONTANT_TTC_INCOHERENT",
    "DATE_EXPIRATION_DEPASSEE": "DATE_EXPIRATION_DEPASSEE",
    "SIRET_MISMATCH": "SIRET_INCOHERENT_MULTI_DOCS",
    "SIRET_INCOHERENT_FACTURE_ATTESTATION": "SIRET_INCOHERENT_FACTURE_ATTESTATION",
    "SIRET_NON_TROUVE": "SIRET_NON_TROUVE",
    "SIRENE_API_INDISPONIBLE": "SIRENE_API_INDISPONIBLE",
    "MISSING_REQUIRED_FIELD": "CHAMP_OBLIGATOIRE_MANQUANT",
    "IBAN_INVALID": "IBAN_INVALIDE",
    "BIC_INVALID": "BIC_INVALIDE",
    "DATE_ECHEANCE_INCOHERENTE": "DATE_ECHEANCE_INCOHERENTE",
    "DATE_VALIDITE_INCOHERENTE": "DATE_VALIDITE_INCOHERENTE",
    "ANOMALY_AMOUNT_OUTLIER": "ANOMALIE_MONTANT",
    "LOW_EXTRACTION_CONFIDENCE": "FAIBLE_CONFIANCE_EXTRACTION",
    "ML_ANOMALY_DETECTED": "ML_ANOMALY_DETECTED",
    "INVOICE_RIB_MISMATCH": "RIB_INCOHERENT_AVEC_FACTURE",
    "ATTESTATION_TOO_OLD": "ATTESTATION_TROP_ANCIENNE",
    "NONSTANDARD_VAT_RATE": "TAUX_TVA_NON_STANDARD",
    "DUPLICATE_INVOICE_SUSPECTED": "DOUBLON_FACTURE_SUSPECT",
    "LOW_CONFIDENCE_CRITICAL_FIELD": "FAIBLE_CONFIANCE_CHAMP_CRITIQUE",
    "VAT_NEGATIVE_AMOUNT": "TVA_NEGATIVE",
    "VAT_TTC_LT_HT": "TTC_INFERIEUR_HT",
    "VAT_ZERO_ON_STANDARD_INVOICE": "TVA_NULLE_A_VERIFIER",
    "DOCUMENT_TOO_INCOMPLETE": "DOCUMENT_TROP_INCOMPLET",
}


class AnomalyEngine:
    def __init__(
        self,
        insee_client: InseeClient,
        anomaly_model: Optional[DocumentAnomalyModel] = None,
        reference_date: Optional[datetime] = None,
        engine_version: str = "1.1.0",
    ):
        self.insee_client = insee_client
        self.anomaly_model = anomaly_model
        self.reference_date = reference_date or datetime.utcnow()
        self.engine_version = engine_version

    def run(self, batch: BatchInput) -> ValidationResult:
        alerts: List[Alert] = []

        for doc in batch.documents:
            alerts.extend(rule_missing_required_fields(doc))
            alerts.extend(rule_document_too_incomplete(doc))
            alerts.extend(rule_siret_format(doc))
            alerts.extend(rule_siren_format(doc))
            alerts.extend(rule_tva_consistency(doc))
            alerts.extend(rule_amount_consistency(doc))
            alerts.extend(rule_nonstandard_vat_rate(doc))
            alerts.extend(rule_vat_business_logic(doc))
            alerts.extend(rule_date_consistency(doc))
            alerts.extend(rule_attestation_expired(doc, self.reference_date))
            alerts.extend(rule_attestation_too_old(doc, self.reference_date))
            alerts.extend(rule_rib_format(doc))
            alerts.extend(rule_reference_format(doc))
            alerts.extend(rule_low_confidence_critical_fields(doc))

        alerts.extend(rule_siret_exists_insee_batch(batch, self.insee_client))
        alerts.extend(rule_siret_mismatch_across_documents(batch))
        alerts.extend(rule_facture_attestation_siret_mismatch(batch))
        alerts.extend(rule_supplier_name_mismatch(batch))
        alerts.extend(rule_invoice_rib_mismatch(batch))
        alerts.extend(rule_duplicate_invoices(batch))
        alerts.extend(rule_fraud_heuristics(batch))

        if self.anomaly_model is not None:
            alerts.extend(self.anomaly_model.analyze_batch(batch))

        alerts = self._collapse_incomplete_document_alerts(alerts)
        alerts = self._deduplicate_alerts(alerts)
        score = self._compute_score(alerts)
        decision = self._compute_decision(score, alerts)
        blocking_reasons = self._build_blocking_reasons(decision, alerts)

        summary = ValidationSummary(
            critical=sum(a.severity == "critical" for a in alerts),
            high=sum(a.severity == "high" for a in alerts),
            medium=sum(a.severity == "medium" for a in alerts),
            low=sum(a.severity == "low" for a in alerts),
        )

        docs_with_alerts = len({
            doc_id
            for alert in alerts
            for doc_id in alert.documents
        })

        batch_stats = BatchStats(
            documents_total=len(batch.documents),
            documents_with_alerts=docs_with_alerts,
            groups_total=len(self._count_groups(batch)),
        )

        return ValidationResult(
            batch_id=batch.batch_id,
            status="completed",
            validated_at=self.reference_date.isoformat(),
            engine_version=self.engine_version,
            global_score=score,
            decision=decision,
            alerts=alerts,
            signals=self._build_signals(alerts),
            summary=summary,
            batch_stats=batch_stats,
            blocking_reasons=blocking_reasons,
        )


    def _count_groups(self, batch: BatchInput):
        return build_document_groups(batch)

    def _compute_score(self, alerts: List[Alert]) -> int:
        return sum(SEVERITY_SCORES[a.severity] for a in alerts)

    def _compute_decision(self, score: int, alerts: List[Alert]) -> str:
        rule_codes = {a.rule_code for a in alerts}

        if score >= 50:
            return "blocked"

        if "SIRENE_API_INDISPONIBLE" in rule_codes:
            return "review"

        if score >= 20:
            return "review"

        return "approved"

    def _deduplicate_alerts(self, alerts: List[Alert]) -> List[Alert]:
        seen = set()
        deduped = []

        for alert in alerts:
            key = (
                alert.rule_code,
                alert.severity,
                tuple(sorted(alert.documents)),
                tuple(sorted((k, str(v)) for k, v in alert.details.items())),
            )
            if key not in seen:
                seen.add(key)
                deduped.append(alert)

        return deduped

    def _build_signals(self, alerts: List[Alert]) -> List[Signal]:
        signals: List[Signal] = []

        for alert in alerts:
            details = alert.details
            value = (
                details.get("tva_number")
                or details.get("siret")
                or details.get("siren")
                or details.get("iban")
                or details.get("bic")
                or details.get("missing_field")
                or details.get("ml_score")
                or details.get("amount_ttc")
                or details.get("confidence")
                or details.get("apparent_rate")
            )

            signals.append(Signal(
                code=RULE_TO_SIGNAL_CODE.get(alert.rule_code, alert.rule_code),
                message=alert.message,
                champ=details.get("champ"),
                valeur=value,
                document_id=alert.documents[0] if alert.documents else None,
            ))

        return signals

    
    
    
    def _build_blocking_reasons(self, decision: str, alerts: List[Alert]) -> List[str]:
        if decision == "approved":
            return []

        if decision == "blocked":
            return sorted({
                alert.rule_code
                for alert in alerts
                if alert.severity in {"critical", "high"}
            })

        
        return sorted({
            alert.rule_code
            for alert in alerts
            if alert.severity in {"critical", "high", "medium"}
        })        
    
    def _collapse_incomplete_document_alerts(self, alerts: List[Alert]) -> List[Alert]:
        incomplete_docs = {
            alert.documents[0]
            for alert in alerts
            if alert.rule_code == "DOCUMENT_TOO_INCOMPLETE" and alert.documents
        }

        collapsed = []
        for alert in alerts:
            if (
                alert.rule_code == "MISSING_REQUIRED_FIELD"
                and len(alert.documents) == 1
                and alert.documents[0] in incomplete_docs
            ):
                continue
            collapsed.append(alert)

        return collapsed        