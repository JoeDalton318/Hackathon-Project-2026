from datetime import datetime
from typing import List, Optional, Tuple

from .insee_client import InseeClient
from .models import Alert, BatchInput, DocumentInput
from .validation_core import (
    CREDIT_NOTE_NUMBER_REGEX,
    INVOICE_NUMBER_REGEX,
    QUOTE_NUMBER_REGEX,
    apparent_vat_rate,
    build_document_groups,
    get_candidate_parties_for_insee,
    get_critical_fields_by_doc_type,
    get_primary_entity_name,
    get_primary_siren,
    get_primary_siret,
    get_supplier_name,
    is_amount_consistent,
    is_valid_bic,
    is_valid_fr_tva,
    is_valid_iban,
    is_valid_siren,
    is_valid_siret,
    matches_regex,
    most_common_name,
    normalize_bic,
    normalize_company_name,
    normalize_digits,
    normalize_iban,
    normalize_text,
    normalize_tva,
    parse_date,
    similarity,
    get_primary_valid_siren,
    get_primary_valid_siret,
)

REQUIRED_BY_DOC_TYPE = {
    "facture": ["numero_facture", "date_facture", "fournisseur", "client", "amount_ttc"],
    "devis": ["numero_devis", "date_devis", "date_validite", "emetteur", "client", "amount_ttc"],
    "avoir": ["numero_avoir", "date_avoir", "reference_facture_origine", "emetteur", "client", "amount_ttc"],
    "bon_de_commande": ["numero_commande", "date_commande", "commanditaire", "fournisseur", "amount_ttc"],
    "bon_de_livraison": ["date_livraison", "client"],
    "attestation": ["date_emission"],
    "attestation_siret": ["siret", "date_emission", "date_expiration"],
    "attestation_vigilance_urssaf": ["date_emission", "date_expiration"],
    "extrait_kbis": ["siren", "siret_siege", "denomination"],
    "rib": ["iban", "bic", "titulaire"],
}

REFERENCE_RULES = [
    ("facture", "numero_facture", INVOICE_NUMBER_REGEX, "INVOICE_NUMBER_INVALID", "Le format du numéro de facture paraît invalide."),
    ("devis", "numero_devis", QUOTE_NUMBER_REGEX, "QUOTE_NUMBER_INVALID", "Le format du numéro de devis paraît invalide."),
    ("avoir", "numero_avoir", CREDIT_NOTE_NUMBER_REGEX, "CREDIT_NOTE_NUMBER_INVALID", "Le format du numéro d'avoir paraît invalide."),
]


def _mk(rule_code: str, severity: str, message: str, documents: List[str], **details) -> Alert:
    return Alert(
        rule_code=rule_code,
        severity=severity,  
        message=message,
        documents=documents,
        details=details,
    )


def _unique_candidates(items: List[Tuple[str, Optional[str]]]) -> List[Tuple[str, str]]:
    seen_values = set()
    output = []

    for field_path, value in items:
        if not value or value in seen_values:
            continue
        seen_values.add(value)
        output.append((field_path, value))

    return output


def _is_party_minimally_filled(party) -> bool:
    if not party:
        return False

    return any([
        party.raison_sociale,
        party.siret,
        party.siren,
        party.tva_intracommunautaire,
        party.email,
        party.telephone,
    ])


def rule_missing_required_fields(doc: DocumentInput) -> List[Alert]:
    alerts = []

    for field_name in REQUIRED_BY_DOC_TYPE.get(doc.doc_type, []):
        value = getattr(doc.fields, field_name, None)

        if field_name in {"fournisseur", "client", "emetteur", "commanditaire", "titulaire_compte"}:
            if not _is_party_minimally_filled(value):
                alerts.append(_mk(
                    "MISSING_REQUIRED_FIELD",
                    "high",
                    f"Champ obligatoire absent ou vide pour le document {doc.doc_type}: {field_name}",
                    [doc.document_id],
                    missing_field=field_name,
                    doc_type=doc.doc_type,
                ))
            continue

        if value in (None, "", []):
            alerts.append(_mk(
                "MISSING_REQUIRED_FIELD",
                "high",
                f"Champ obligatoire absent pour le document {doc.doc_type}: {field_name}",
                [doc.document_id],
                missing_field=field_name,
                doc_type=doc.doc_type,
            ))

    return alerts

def rule_document_too_incomplete(doc: DocumentInput, min_missing_critical_fields: int = 3) -> List[Alert]:
    critical_fields = get_critical_fields_by_doc_type(doc.doc_type)
    if not critical_fields:
        return []

    missing_fields = []

    for field_name in critical_fields:
        value = getattr(doc.fields, field_name, None)

        if field_name in {"fournisseur", "client", "emetteur", "commanditaire", "titulaire_compte"}:
            if not _is_party_minimally_filled(value):
                missing_fields.append(field_name)
            continue

        if value in (None, "", []):
            missing_fields.append(field_name)

    if len(missing_fields) >= min_missing_critical_fields:
        return [_mk(
            "DOCUMENT_TOO_INCOMPLETE",
            "high",
            "Le document est trop incomplet pour une validation fiable.",
            [doc.document_id],
            doc_type=doc.doc_type,
            missing_fields=missing_fields,
            missing_count=len(missing_fields),
            threshold=min_missing_critical_fields,
        )]

    return []

def rule_siret_format(doc: DocumentInput) -> List[Alert]:
    alerts = []
    candidates = []

    primary = get_primary_siret(doc)
    if primary:
        candidates.append(("document.siret", primary))

    for label, party in get_candidate_parties_for_insee(doc):
        if party and party.siret:
            candidates.append((f"{label}.siret", normalize_digits(party.siret)))

    for field_path, value in _unique_candidates(candidates):
        if not is_valid_siret(value):
            alerts.append(_mk(
                "SIRET_INVALID",
                "high",
                "Le SIRET est invalide (regex, longueur ou checksum Luhn).",
                [doc.document_id],
                champ=field_path,
                siret=value,
            ))
    return alerts


def rule_siren_format(doc: DocumentInput) -> List[Alert]:
    alerts = []
    candidates = []

    primary = get_primary_siren(doc)
    if primary:
        candidates.append(("document.siren", primary))

    for label, party in get_candidate_parties_for_insee(doc):
        if party and party.siren:
            candidates.append((f"{label}.siren", normalize_digits(party.siren)))

    for field_path, value in _unique_candidates(candidates):
        if not is_valid_siren(value):
            alerts.append(_mk(
                "SIREN_INVALID",
                "medium",
                "Le SIREN est invalide (regex, longueur ou checksum Luhn).",
                [doc.document_id],
                champ=field_path,
                siren=value,
            ))
    return alerts


def rule_tva_consistency(doc: DocumentInput) -> List[Alert]:
    tva_number = normalize_tva(doc.fields.tva_number)
    siren = get_primary_siren(doc)

    if doc.fields.fournisseur and doc.fields.fournisseur.tva_intracommunautaire:
        tva_number = normalize_tva(doc.fields.fournisseur.tva_intracommunautaire)
        if doc.fields.fournisseur.siren:
            siren = normalize_digits(doc.fields.fournisseur.siren)
        elif doc.fields.fournisseur.siret:
            supplier_siret = normalize_digits(doc.fields.fournisseur.siret)
            siren = supplier_siret[:9] if supplier_siret else None

    if tva_number and not is_valid_fr_tva(tva_number, siren):
        return [_mk(
            "TVA_INVALID",
            "high",
            "Le numéro de TVA est invalide ou incohérent avec le SIREN.",
            [doc.document_id],
            tva_number=tva_number,
            siren=siren,
        )]

    return []


def rule_amount_consistency(doc: DocumentInput) -> List[Alert]:
    if doc.doc_type not in {"facture", "devis", "avoir", "bon_de_commande"}:
        return []

    if None in (doc.fields.amount_ht, doc.fields.amount_tva, doc.fields.amount_ttc):
        return []

    if is_amount_consistent(doc.fields.amount_ht, doc.fields.amount_tva, doc.fields.amount_ttc):
        return []

    return [_mk(
        "VAT_AMOUNT_MISMATCH",
        "medium",
        "Le montant TTC est incohérent avec HT + TVA.",
        [doc.document_id],
        amount_ht=doc.fields.amount_ht,
        amount_tva=doc.fields.amount_tva,
        amount_ttc=doc.fields.amount_ttc,
    )]


def rule_date_consistency(doc: DocumentInput) -> List[Alert]:
    alerts = []

    if doc.doc_type == "facture":
        invoice_raw = doc.fields.date_facture or doc.fields.invoice_date
        due_raw = doc.fields.date_echeance
        invoice_date = parse_date(invoice_raw)
        due_date = parse_date(due_raw)

        if due_raw and not due_date:
            alerts.append(_mk(
                "DATE_ECHEANCE_INVALID",
                "medium",
                "La date d'échéance n'est pas lisible.",
                [doc.document_id],
                date_echeance=due_raw,
            ))
        elif invoice_date and due_date and due_date < invoice_date:
            alerts.append(_mk(
                "DATE_ECHEANCE_INCOHERENTE",
                "medium",
                "La date d'échéance est antérieure à la date de facture.",
                [doc.document_id],
                date_facture=invoice_raw,
                date_echeance=due_raw,
            ))

    if doc.doc_type == "devis":
        d1 = parse_date(doc.fields.date_devis)
        d2 = parse_date(doc.fields.date_validite)
        if d1 and d2 and d2 < d1:
            alerts.append(_mk(
                "DATE_VALIDITE_INCOHERENTE",
                "medium",
                "La date de validité du devis est antérieure à la date du devis.",
                [doc.document_id],
                date_devis=doc.fields.date_devis,
                date_validite=doc.fields.date_validite,
            ))

    return alerts


def rule_attestation_expired(doc: DocumentInput, reference_date: datetime) -> List[Alert]:
    if doc.doc_type not in {"attestation", "attestation_siret", "attestation_vigilance", "attestation_vigilance_urssaf"}:
        return []

    expiry_raw = doc.fields.date_expiration or doc.fields.expiry_date
    expiry = parse_date(expiry_raw)

    if expiry_raw and not expiry:
        return [_mk(
            "EXPIRY_DATE_UNPARSEABLE",
            "medium",
            "La date d'expiration de l'attestation n'est pas lisible.",
            [doc.document_id],
            expiry_date=expiry_raw,
        )]

    if expiry and expiry.date() < reference_date.date():
        return [_mk(
            "DATE_EXPIRATION_DEPASSEE",
            "high",
            "La date d'expiration de l'attestation est dépassée.",
            [doc.document_id],
            expiry_date=expiry_raw,
            reference_date=reference_date.strftime("%Y-%m-%d"),
        )]

    return []

def rule_rib_format(doc: DocumentInput) -> List[Alert]:
    if doc.doc_type != "rib":
        return []

    alerts = []
    iban = normalize_iban(doc.fields.iban)
    bic = normalize_bic(doc.fields.bic)

    if iban and not is_valid_iban(iban):
        alerts.append(_mk(
            "IBAN_INVALID",
            "high",
            "Le format ou le checksum de l'IBAN est invalide.",
            [doc.document_id],
            iban=iban,
        ))

    if bic and not is_valid_bic(bic):
        alerts.append(_mk(
            "BIC_INVALID",
            "medium",
            "Le format du BIC est invalide.",
            [doc.document_id],
            bic=bic,
        ))

    return alerts


def rule_reference_format(doc: DocumentInput) -> List[Alert]:
    alerts = []
    for doc_type, field_name, regex, code, message in REFERENCE_RULES:
        value = getattr(doc.fields, field_name, None)
        if doc.doc_type == doc_type and value and not matches_regex(value, regex):
            alerts.append(_mk(code, "low", message, [doc.document_id], **{field_name: value}))
    return alerts



def rule_siret_exists_insee_batch(batch: BatchInput, insee_client: InseeClient) -> List[Alert]:
    alerts = []
    siret_to_docs = {}

    for doc in batch.documents:
        doc_sirets = set()

        primary_siret = get_primary_siret(doc)
        if primary_siret:
            doc_sirets.add(primary_siret)

        for _, party in get_candidate_parties_for_insee(doc):
            if party and party.siret:
                normalized = normalize_digits(party.siret)
                if normalized:
                    doc_sirets.add(normalized)

        for siret in doc_sirets:
            siret_to_docs.setdefault(siret, set()).add(doc.document_id)

    for siret in sorted(siret_to_docs):
        if not is_valid_siret(siret):
            continue

        result = insee_client.get_establishment(siret)
        related_docs = sorted(siret_to_docs[siret])

        if result["status"] in {"error", "api_error_mock_fallback", "api_exception_mock_fallback"}:
            alerts.append(_mk(
                "SIRENE_API_INDISPONIBLE",
                "medium",
                "Impossible de vérifier le SIRET : API SIRENE temporairement indisponible.",
                related_docs,
                siret=siret,
                lookup_status=result["status"],
            ))
        elif not result["found"]:
            alerts.append(_mk(
                "SIRET_NON_TROUVE",
                "high",
                "Le SIRET n'a pas été trouvé dans la base SIRENE / INSEE.",
                related_docs,
                siret=siret,
                lookup_status=result["status"],
            ))

    return alerts

def rule_siret_mismatch_across_documents(batch: BatchInput) -> List[Alert]:
    alerts = []
    groups = build_document_groups(batch)

    for group_key, docs in groups.items():
        docs_with_siret = [
            (doc.document_id, get_primary_siret(doc))
            for doc in docs
        ]
        docs_with_siret = [(doc_id, siret) for doc_id, siret in docs_with_siret if siret]

        unique_sirets = sorted({siret for _, siret in docs_with_siret})

        if len(unique_sirets) <= 1:
            continue

        alerts.append(_mk(
            "SIRET_MISMATCH",
            "critical",
            "Incohérence de SIRET entre documents d'un même groupe fournisseur.",
            [doc_id for doc_id, _ in docs_with_siret],
            sirets_found=unique_sirets,
            group_key=group_key,
        ))

    return alerts

def rule_facture_attestation_siret_mismatch(batch: BatchInput) -> List[Alert]:
    alerts = []
    groups = build_document_groups(batch)

    for group_key, docs in groups.items():
        factures = [d for d in docs if d.doc_type == "facture"]
        attestations = [
            d for d in docs
            if d.doc_type in {
                "attestation",
                "attestation_siret",
                "attestation_vigilance",
                "attestation_vigilance_urssaf",
            }
        ]

        for facture in factures:
            facture_siret = get_primary_siret(facture)
            if not facture_siret:
                continue

            for attestation in attestations:
                attestation_siret = get_primary_siret(attestation)
                if attestation_siret and facture_siret != attestation_siret:
                    alerts.append(_mk(
                        "SIRET_INCOHERENT_FACTURE_ATTESTATION",
                        "critical",
                        "Le SIRET de la facture est incohérent avec celui de l'attestation.",
                        [facture.document_id, attestation.document_id],
                        facture_siret=facture_siret,
                        attestation_siret=attestation_siret,
                        group_key=group_key,
                    ))

    return alerts


def rule_supplier_name_mismatch(batch: BatchInput) -> List[Alert]:
    alerts = []
    groups = build_document_groups(batch)

    for group_key, docs in groups.items():
        names_by_doc = {}

        for doc in docs:
            name = get_primary_entity_name(doc)
            if name:
                names_by_doc[doc.document_id] = name

        if len(names_by_doc) < 2:
            continue

        reference_name = most_common_name(list(names_by_doc.values()))
        if not reference_name:
            continue

        mismatching_docs = [
            doc_id for doc_id, name in names_by_doc.items()
            if similarity(name, reference_name) < 0.80
        ]

        if mismatching_docs:
            alerts.append(_mk(
                "SUPPLIER_NAME_MISMATCH",
                "medium",
                "Le nom fournisseur est incohérent dans un même groupe documentaire.",
                mismatching_docs,
                reference_name=reference_name,
                names_found=names_by_doc,
                group_key=group_key,
            ))

    return alerts

def rule_invoice_rib_mismatch(batch: BatchInput) -> List[Alert]:
    alerts = []

    factures = [d for d in batch.documents if d.doc_type == "facture"]
    ribs = [d for d in batch.documents if d.doc_type == "rib"]

    if not factures or not ribs:
        return alerts

    for facture in factures:
        facture_name = normalize_company_name(get_supplier_name(facture))
        facture_siret = get_primary_siret(facture)

        for rib in ribs:
            rib_name = normalize_company_name(
                rib.fields.titulaire
                or (rib.fields.titulaire_compte.raison_sociale if rib.fields.titulaire_compte else None)
                or rib.fields.supplier_name
            )
            rib_siret = get_primary_siret(rib)

            
            if facture_siret and rib_siret:
                if facture_siret != rib_siret:
                    alerts.append(_mk(
                        "INVOICE_RIB_MISMATCH",
                        "high",
                        "Incohérence forte entre le fournisseur de la facture et le titulaire du RIB (SIRET différents).",
                        [facture.document_id, rib.document_id],
                        facture_name=facture_name,
                        rib_name=rib_name,
                        facture_siret=facture_siret,
                        rib_siret=rib_siret,
                        mismatch_basis="siret",
                    ))
                continue

            
            if facture_name and rib_name:
                sim = similarity(facture_name, rib_name)

                if sim < 0.60:
                    alerts.append(_mk(
                        "INVOICE_RIB_MISMATCH",
                        "medium",
                        "Incohérence possible entre le fournisseur de la facture et le titulaire du RIB (noms très différents).",
                        [facture.document_id, rib.document_id],
                        facture_name=facture_name,
                        rib_name=rib_name,
                        similarity=round(sim, 3),
                        mismatch_basis="name",
                    ))

    return alerts


def rule_attestation_too_old(doc: DocumentInput, reference_date: datetime, max_age_days: int = 180) -> List[Alert]:
    if doc.doc_type not in {"attestation", "attestation_siret", "attestation_vigilance", "attestation_vigilance_urssaf"}:
        return []

    emission_raw = doc.fields.date_emission or doc.fields.issue_date
    emission_date = parse_date(emission_raw)

    if not emission_date:
        return []

    age_days = (reference_date.date() - emission_date.date()).days

    if age_days > max_age_days:
        return [_mk(
            "ATTESTATION_TOO_OLD",
            "medium",
            "L'attestation est ancienne et mérite une revue.",
            [doc.document_id],
            date_emission=emission_raw,
            age_days=age_days,
            max_age_days=max_age_days,
        )]

    return []


def rule_nonstandard_vat_rate(doc: DocumentInput, tolerance: float = 0.02) -> List[Alert]:
    if doc.doc_type not in {"facture", "devis", "avoir", "bon_de_commande"}:
        return []

    rate = apparent_vat_rate(doc.fields.amount_ht, doc.fields.amount_tva)
    if rate is None:
        return []

    standard_rates = [0.0, 0.021, 0.055, 0.10, 0.20]
    closest = min(standard_rates, key=lambda x: abs(x - rate))

    if abs(rate - closest) > tolerance:
        return [_mk(
            "NONSTANDARD_VAT_RATE",
            "medium",
            "Le taux de TVA apparent ne correspond pas à un taux standard attendu.",
            [doc.document_id],
            apparent_rate=round(rate, 4),
            closest_standard_rate=closest,
        )]

    return []

def rule_vat_business_logic(doc: DocumentInput) -> List[Alert]:
    if doc.doc_type not in {"facture", "devis", "avoir", "bon_de_commande"}:
        return []

    alerts = []

    amount_ht = doc.fields.amount_ht
    amount_tva = doc.fields.amount_tva
    amount_ttc = doc.fields.amount_ttc

    if amount_ht is None or amount_tva is None or amount_ttc is None:
        return alerts

    if amount_tva < 0:
        alerts.append(_mk(
            "VAT_NEGATIVE_AMOUNT",
            "high",
            "Le montant de TVA est négatif, ce qui est incohérent pour ce document.",
            [doc.document_id],
            amount_ht=amount_ht,
            amount_tva=amount_tva,
            amount_ttc=amount_ttc,
        ))

    if amount_ttc < amount_ht:
        alerts.append(_mk(
            "VAT_TTC_LT_HT",
            "high",
            "Le montant TTC est inférieur au montant HT, ce qui est incohérent.",
            [doc.document_id],
            amount_ht=amount_ht,
            amount_tva=amount_tva,
            amount_ttc=amount_ttc,
        ))

   
    if doc.doc_type == "facture" and amount_ht > 0 and amount_tva == 0:
        alerts.append(_mk(
            "VAT_ZERO_ON_STANDARD_INVOICE",
            "medium",
            "TVA nulle sur une facture avec montant HT positif : vérifier s'il s'agit d'une exonération ou d'une extraction incorrecte.",
            [doc.document_id],
            amount_ht=amount_ht,
            amount_tva=amount_tva,
            amount_ttc=amount_ttc,
        ))

    return alerts

def rule_duplicate_invoices(batch: BatchInput) -> List[Alert]:
    alerts = []
    seen = {}

    for doc in batch.documents:
        if doc.doc_type != "facture":
            continue

        supplier_name = normalize_company_name(get_supplier_name(doc))
        invoice_number = normalize_text(doc.fields.numero_facture)
        amount_ttc = doc.fields.amount_ttc

        if not invoice_number or amount_ttc is None:
            continue

        key = (supplier_name, invoice_number, round(float(amount_ttc), 2))

        if key in seen:
            first_doc_id = seen[key]
            alerts.append(_mk(
                "DUPLICATE_INVOICE_SUSPECTED",
                "high",
                "Suspicion de doublon de facture dans le batch.",
                [first_doc_id, doc.document_id],
                supplier_name=supplier_name,
                numero_facture=invoice_number,
                amount_ttc=amount_ttc,
            ))
        else:
            seen[key] = doc.document_id

    return alerts


def rule_low_confidence_critical_fields(doc: DocumentInput, threshold: float = 0.60) -> List[Alert]:
    alerts = []

    field_conf = doc.metadata.get("field_confidence", {})
    critical_fields = get_critical_fields_by_doc_type(doc.doc_type)

    for field_name in critical_fields:
        score = field_conf.get(field_name)
        if score is None:
            continue

        if float(score) < threshold:
            alerts.append(_mk(
                "LOW_CONFIDENCE_CRITICAL_FIELD",
                "low",
                "Champ critique extrait avec une confiance OCR faible.",
                [doc.document_id],
                champ=field_name,
                confidence=float(score),
                threshold=threshold,
            ))

    return alerts


def rule_fraud_heuristics(batch: BatchInput) -> List[Alert]:
    alerts = []

    for doc in batch.documents:
        if doc.doc_type != "facture":
            continue

        if doc.fields.amount_ttc is not None and doc.fields.amount_ttc > 1_000_000:
            alerts.append(_mk(
                "ANOMALY_AMOUNT_OUTLIER",
                "medium",
                "Montant TTC anormalement élevé pour une facture.",
                [doc.document_id],
                amount_ttc=doc.fields.amount_ttc,
            ))

        if doc.fields.confidence is not None and doc.fields.confidence < 0.50:
            alerts.append(_mk(
                "LOW_EXTRACTION_CONFIDENCE",
                "medium",
                "Le score de confiance d'extraction est faible.",
                [doc.document_id],
                confidence=doc.fields.confidence,
            ))

    return alerts