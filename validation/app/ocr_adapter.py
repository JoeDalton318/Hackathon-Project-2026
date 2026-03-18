from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from .minio_io import MinioIO
from .models import BatchInput, DocumentFields, DocumentInput, Party


DOC_TYPE_TO_PAYLOAD_KEY = {
    "facture": "facture",
    "devis": "devis",
    "attestation_siret": "attestation_siret",
    "attestation_vigilance_urssaf": "attestation_urssaf",
    "extrait_kbis": "kbis",
    "rib": "rib",
}


def load_ocr_batch_from_minio(
    batch_id: str,
    limit: int | None = None,
    document_ids: list[str] | None = None,
    file_names: list[str] | None = None,
    endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    secure: bool | None = None,
    bucket: str | None = None,
    prefix: str | None = None,
) -> BatchInput:
    io_client = MinioIO(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
        bucket=bucket,
        input_prefix=prefix,
    )

    objects = io_client.load_input_payloads(
        limit=limit,
        document_ids=document_ids,
        file_names=file_names,
    )

    if not objects:
        raise FileNotFoundError(
            f"Aucun JSON OCR trouvé dans MinIO bucket={io_client.bucket} prefix={io_client.input_prefix}"
        )

    documents = [
        extraction_result_to_document(
            obj.payload,
            source_extraction_key=obj.object_name,
        )
        for obj in objects
    ]
    return BatchInput(batch_id=batch_id, documents=documents)


def _field_value(field: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(field, dict):
        return None
    value = field.get("value")
    if value is None:
        return None
    return str(value).strip()


def _field_confidence(field: Optional[Dict[str, Any]]) -> Optional[float]:
    if not isinstance(field, dict):
        return None
    conf = field.get("confidence")
    if conf is None:
        return None
    try:
        return float(conf)
    except (TypeError, ValueError):
        return None


def _to_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("€", "")
    s = s.replace("EUR", "")
    s = s.replace("\xa0", " ")
    s = s.replace(" ", "")
    s = s.replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)

    if not s:
        return None

    try:
        return float(s)
    except ValueError:
        return None


def _extract_party(info: Optional[Dict[str, Any]]) -> Optional[Party]:
    if not isinstance(info, dict):
        return None

    party = Party(
        raison_sociale=_field_value(info.get("nom")),
        siret=_field_value(info.get("siret")),
        siren=_field_value(info.get("siren")),
        tva_intracommunautaire=_field_value(info.get("tva_intracom")),
        adresse={
            "adresse": _field_value(info.get("adresse")),
            "code_postal": _field_value(info.get("code_postal")),
            "ville": _field_value(info.get("ville")),
        },
        email=_field_value(info.get("email")),
        telephone=_field_value(info.get("telephone")),
    )

    if not any([
        party.raison_sociale,
        party.siret,
        party.siren,
        party.tva_intracommunautaire,
        party.email,
        party.telephone,
    ]):
        return None

    return party


def _build_field_confidence(doc_type: str, typed_data: Dict[str, Any]) -> Dict[str, float]:
    result: Dict[str, float] = {}

    def add(target_name: str, field: Optional[Dict[str, Any]]) -> None:
        conf = _field_confidence(field)
        if conf is not None:
            result[target_name] = conf

    if doc_type == "facture":
        add("numero_facture", typed_data.get("numero_facture"))
        add("date_facture", typed_data.get("date_emission"))
        add("date_echeance", typed_data.get("date_echeance"))
        add("amount_ht", typed_data.get("montant_ht"))
        add("amount_tva", typed_data.get("montant_tva"))
        add("amount_ttc", typed_data.get("montant_ttc"))
        add("taux_tva", typed_data.get("taux_tva"))

        emetteur = typed_data.get("emetteur", {})
        add("siret", emetteur.get("siret"))
        add("siren", emetteur.get("siren"))
        add("tva_number", emetteur.get("tva_intracom"))
        add("iban", emetteur.get("iban"))
        add("bic", emetteur.get("bic"))

    elif doc_type == "devis":
        add("numero_devis", typed_data.get("numero_devis"))
        add("date_devis", typed_data.get("date_emission"))
        add("date_validite", typed_data.get("date_validite"))
        add("amount_ht", typed_data.get("montant_ht"))
        add("amount_ttc", typed_data.get("montant_ttc"))

        emetteur = typed_data.get("emetteur", {})
        add("siret", emetteur.get("siret"))
        add("siren", emetteur.get("siren"))
        add("tva_number", emetteur.get("tva_intracom"))

    elif doc_type == "attestation_siret":
        add("denomination", typed_data.get("denomination"))
        add("siret", typed_data.get("siret"))
        add("siren", typed_data.get("siren"))

    elif doc_type == "attestation_vigilance_urssaf":
        add("denomination", typed_data.get("denomination"))
        add("siret", typed_data.get("siret"))
        add("date_emission", typed_data.get("date_emission"))
        add("date_expiration", typed_data.get("date_expiration"))

    elif doc_type == "extrait_kbis":
        add("denomination", typed_data.get("denomination"))
        add("siren", typed_data.get("siren"))

    elif doc_type == "rib":
        add("iban", typed_data.get("iban"))
        add("bic", typed_data.get("bic"))
        add("banque", typed_data.get("banque"))

        titulaire = typed_data.get("titulaire", {})
        add("titulaire", titulaire.get("nom"))
        add("siret", titulaire.get("siret"))
        add("siren", titulaire.get("siren"))

    return result


def extraction_result_to_document(
    payload: Dict[str, Any],
    source_extraction_key: str | None = None,
) -> DocumentInput:
    document_id = payload["document_id"]
    file_name = payload.get("file_name")
    classification = payload.get("classification", {})
    doc_type = classification.get("document_type", "inconnu")
    classification_confidence = classification.get("confidence")
    overall_confidence = payload.get("overall_confidence")
    raw_text = payload.get("raw_text", "")
    ocr_metadata = payload.get("ocr_metadata", {})
    ocr_confidence = ocr_metadata.get("ocr_confidence_avg")

    payload_key = DOC_TYPE_TO_PAYLOAD_KEY.get(doc_type, doc_type)
    typed_data = payload.get(payload_key) or {}

    fields = DocumentFields(
        confidence=overall_confidence,
        raw_text=raw_text,
        file_name=file_name,
        classification_confidence=classification_confidence,
        ocr_confidence=ocr_confidence,
    )

    if doc_type == "facture":
        emetteur = typed_data.get("emetteur", {})
        destinataire = typed_data.get("destinataire", {})

        fields.numero_facture = _field_value(typed_data.get("numero_facture"))
        fields.date_facture = _field_value(typed_data.get("date_emission"))
        fields.invoice_date = _field_value(typed_data.get("date_emission"))
        fields.date_emission = _field_value(typed_data.get("date_emission"))
        fields.date_echeance = _field_value(typed_data.get("date_echeance"))

        fields.amount_ht = _to_float(_field_value(typed_data.get("montant_ht")))
        fields.amount_tva = _to_float(_field_value(typed_data.get("montant_tva")))
        fields.amount_ttc = _to_float(_field_value(typed_data.get("montant_ttc")))
        fields.taux_tva = _field_value(typed_data.get("taux_tva"))

        fields.fournisseur = _extract_party(emetteur)
        fields.emetteur = _extract_party(emetteur)
        fields.client = _extract_party(destinataire)
        fields.destinataire = _extract_party(destinataire)

        fields.supplier_name = _field_value(emetteur.get("nom"))
        fields.siret = _field_value(emetteur.get("siret"))
        fields.siren = _field_value(emetteur.get("siren"))
        fields.tva_number = _field_value(emetteur.get("tva_intracom"))
        fields.iban = _field_value(emetteur.get("iban"))
        fields.bic = _field_value(emetteur.get("bic"))

    elif doc_type == "devis":
        emetteur = typed_data.get("emetteur", {})
        client = typed_data.get("client", {})

        fields.numero_devis = _field_value(typed_data.get("numero_devis"))
        fields.date_devis = _field_value(typed_data.get("date_emission"))
        fields.date_emission = _field_value(typed_data.get("date_emission"))
        fields.date_validite = _field_value(typed_data.get("date_validite"))

        fields.amount_ht = _to_float(_field_value(typed_data.get("montant_ht")))
        fields.amount_ttc = _to_float(_field_value(typed_data.get("montant_ttc")))

        fields.emetteur = _extract_party(emetteur)
        fields.client = _extract_party(client)

        fields.supplier_name = _field_value(emetteur.get("nom"))
        fields.siret = _field_value(emetteur.get("siret"))
        fields.siren = _field_value(emetteur.get("siren"))
        fields.tva_number = _field_value(emetteur.get("tva_intracom"))

    elif doc_type == "attestation_siret":
        fields.denomination = _field_value(typed_data.get("denomination"))
        fields.supplier_name = _field_value(typed_data.get("denomination"))
        fields.siret = _field_value(typed_data.get("siret"))
        fields.siren = _field_value(typed_data.get("siren"))
        fields.siret_siege = _field_value(typed_data.get("siret"))

    elif doc_type == "attestation_vigilance_urssaf":
        fields.denomination = _field_value(typed_data.get("denomination"))
        fields.supplier_name = _field_value(typed_data.get("denomination"))
        fields.siret = _field_value(typed_data.get("siret"))
        fields.siren = _field_value(typed_data.get("siret"))[:9] if _field_value(typed_data.get("siret")) else None
        fields.date_emission = _field_value(typed_data.get("date_emission"))
        fields.issue_date = _field_value(typed_data.get("date_emission"))
        fields.date_expiration = _field_value(typed_data.get("date_expiration"))
        fields.expiry_date = _field_value(typed_data.get("date_expiration"))

    elif doc_type == "extrait_kbis":
        fields.denomination = _field_value(typed_data.get("denomination"))
        fields.supplier_name = _field_value(typed_data.get("denomination"))
        fields.siren = _field_value(typed_data.get("siren"))

    elif doc_type == "rib":
        titulaire = typed_data.get("titulaire", {})

        fields.titulaire = _field_value(titulaire.get("nom"))
        fields.titulaire_compte = _extract_party(titulaire)
        fields.banque = _field_value(typed_data.get("banque"))
        fields.iban = _field_value(typed_data.get("iban"))
        fields.bic = _field_value(typed_data.get("bic"))

        fields.supplier_name = _field_value(titulaire.get("nom"))
        fields.siret = _field_value(titulaire.get("siret"))
        fields.siren = _field_value(titulaire.get("siren"))

    metadata = {
        "source": "nlp_ocr",
        "file_name": file_name,
        "ocr_metadata": ocr_metadata,
        "classification": classification,
        "raw_text_length": len(raw_text or ""),
        "extraction_warnings": payload.get("extraction_warnings", []),
        "field_confidence": _build_field_confidence(doc_type, typed_data),
        "source_extraction_key": source_extraction_key,
    }

    return DocumentInput(
        document_id=document_id,
        doc_type=doc_type,
        fields=fields,
        metadata=metadata,
    )


def load_ocr_json_file(file_path: Path) -> DocumentInput:
    with open(file_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return extraction_result_to_document(payload, source_extraction_key=str(file_path))


def load_ocr_batch_from_dir(
    input_dir: Path,
    batch_id: str,
    limit: int | None = None,
    document_ids: list[str] | None = None,
    file_names: list[str] | None = None,
) -> BatchInput:
    files = sorted(input_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"Aucun fichier JSON trouvé dans {input_dir}")

    wanted_ids = set(document_ids or [])
    wanted_files = set(file_names or [])

    documents: list[DocumentInput] = []

    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        payload_document_id = payload.get("document_id")
        payload_file_name = payload.get("file_name")

        if wanted_ids and payload_document_id not in wanted_ids:
            continue

        if wanted_files and payload_file_name not in wanted_files:
            continue

        documents.append(
            extraction_result_to_document(
                payload,
                source_extraction_key=str(path),
            )
        )

        if limit is not None and len(documents) >= limit:
            break

    if not documents:
        raise FileNotFoundError("Aucun document OCR ne correspond aux filtres demandés.")

    return BatchInput(batch_id=batch_id, documents=documents)