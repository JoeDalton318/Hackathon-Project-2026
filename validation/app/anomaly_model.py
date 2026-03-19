from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from .models import Alert, BatchInput, DocumentInput
from .validation_core import (
    get_primary_siren,
    get_primary_siret,
    is_valid_fr_tva,
    is_valid_iban,
    is_valid_siret,
    normalize_iban,
    normalize_tva,
    parse_date,
)


class DocumentAnomalyModel:
    """
    Modèle ML complémentaire en plus des règles métier.

    """

    def __init__(
        self,
        contamination: float = 0.10,
        random_state: int = 42,
        enabled: bool = True,
        reference_date: Optional[datetime] = None,
    ):
        self.enabled = enabled
        self.contamination = contamination
        self.random_state = random_state
        self.reference_date = reference_date or datetime.utcnow()
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
        )
        self.is_fitted = False

    def _safe_float(self, value: Optional[float], default: float = 0.0) -> float:
        return default if value is None else float(value)

    def _days_between(self, start_raw: Optional[str], end_raw: Optional[str], default: float = -1.0) -> float:
        start = parse_date(start_raw)
        end = parse_date(end_raw)
        if not start or not end:
            return default
        return float((end - start).days)

    def _days_until(self, target_raw: Optional[str], default: float = -1.0) -> float:
        target = parse_date(target_raw)
        if not target:
            return default
        return float((target.date() - self.reference_date.date()).days)

    def _doc_type_flags(self, doc_type: str) -> List[float]:
        known_types = [
            "facture",
            "devis",
            "avoir",
            "bon_de_commande",
            "attestation",
            "attestation_siret",
            "attestation_vigilance",
            "attestation_vigilance_urssaf",
            "rib",
            "extrait_kbis",
        ]
        return [1.0 if doc_type == t else 0.0 for t in known_types]

    def _extract_features(self, doc: DocumentInput) -> np.ndarray:
        siret = get_primary_siret(doc)
        siren = get_primary_siren(doc)

        tva_number = normalize_tva(doc.fields.tva_number)
        if doc.fields.fournisseur and doc.fields.fournisseur.tva_intracommunautaire:
            tva_number = normalize_tva(doc.fields.fournisseur.tva_intracommunautaire)

        iban = normalize_iban(doc.fields.iban)

        amount_ht = self._safe_float(doc.fields.amount_ht)
        amount_tva = self._safe_float(doc.fields.amount_tva)
        amount_ttc = self._safe_float(doc.fields.amount_ttc)

        tva_ratio = 0.0
        if amount_ht != 0:
            tva_ratio = amount_tva / amount_ht

        days_due_after_invoice = self._days_between(
            doc.fields.date_facture or doc.fields.invoice_date,
            doc.fields.date_echeance,
        )

        days_until_expiry = self._days_until(doc.fields.date_expiration or doc.fields.expiry_date)
        confidence = float(doc.fields.confidence) if doc.fields.confidence is not None else 1.0
        line_count = float(len(doc.fields.lignes)) if doc.fields.lignes else 0.0

        features = []
        features.extend(self._doc_type_flags(doc.doc_type))
        features.extend([
            amount_ht,
            amount_tva,
            amount_ttc,
            tva_ratio,
            days_due_after_invoice,
            days_until_expiry,
            1.0 if siret else 0.0,
            1.0 if (siret and is_valid_siret(siret)) else 0.0,
            1.0 if tva_number else 0.0,
            1.0 if (tva_number and siren and is_valid_fr_tva(tva_number, siren)) else 0.0,
            1.0 if iban else 0.0,
            1.0 if (iban and is_valid_iban(iban)) else 0.0,
            confidence,
            line_count,
        ])

        return np.array(features, dtype=float)

    def fit(self, batches: List[BatchInput]) -> None:
        if not self.enabled:
            return

        rows = []
        for batch in batches:
            for doc in batch.documents:
                rows.append(self._extract_features(doc))

        if len(rows) < 5:
            raise ValueError("Pas assez de données pour entraîner le modèle. Il faut au moins 5 documents normaux.")

        X = np.vstack(rows)
        self.model.fit(X)
        self.is_fitted = True

    def save(self, filepath: str = "artifacts/anomaly_model.joblib") -> None:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model": self.model,
                "is_fitted": self.is_fitted,
                "contamination": self.contamination,
                "random_state": self.random_state,
                "enabled": self.enabled,
            },
            filepath,
        )

    @classmethod
    def load(cls, filepath: str = "artifacts/anomaly_model.joblib") -> "DocumentAnomalyModel":
        payload = joblib.load(filepath)
        obj = cls(
            contamination=payload.get("contamination", 0.10),
            random_state=payload.get("random_state", 42),
            enabled=payload.get("enabled", True),
        )
        obj.model = payload["model"]
        obj.is_fitted = payload.get("is_fitted", True)
        return obj

    def analyze_batch(self, batch: BatchInput) -> List[Alert]:
        alerts: List[Alert] = []

        if not self.enabled or not self.is_fitted:
            return alerts

        for doc in batch.documents:
            x = self._extract_features(doc).reshape(1, -1)
            prediction = self.model.predict(x)[0]
            score = float(self.model.decision_function(x)[0])

            if prediction == -1 and score <= -0.02:
                severity = "high" if score < -0.05 else "medium"

                alerts.append(Alert(
                    rule_code="ML_ANOMALY_DETECTED",
                    severity=severity,  # type: ignore[arg-type]
                    message="Le modèle d'anomaly detection considère ce document comme atypique.",
                    documents=[doc.document_id],
                    details={
                        "ml_model": "IsolationForest",
                        "ml_prediction": int(prediction),
                        "ml_score": round(score, 6),
                        "doc_type": doc.doc_type,
                        "amount_ttc": doc.fields.amount_ttc,
                        "confidence": doc.fields.confidence,
                    },
                ))

        return alerts