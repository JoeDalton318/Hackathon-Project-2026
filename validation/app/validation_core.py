import re
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from .models import BatchInput, DocumentInput, Party

SIREN_REGEX = r"^\d{9}$"
SIRET_REGEX = r"^\d{14}$"
TVA_FR_REGEX = r"^FR[0-9A-Z]{2}\d{9}$"
BIC_REGEX = r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$"

INVOICE_NUMBER_REGEX = r"^[A-Z0-9][A-Z0-9\-_\/]{2,50}$"
QUOTE_NUMBER_REGEX = r"^[A-Z0-9][A-Z0-9\-_\/]{2,50}$"
CREDIT_NOTE_NUMBER_REGEX = r"^[A-Z0-9][A-Z0-9\-_\/]{2,50}$"

LEGAL_SUFFIXES = {
    "SARL",
    "SAS",
    "SASU",
    "EURL",
    "SA",
    "SCI",
    "SC",
    "SNC",
    "SELARL",
    "SELAS",
    "EI",
    "MICRO",
    "ENTREPRISE",
    "AUTOENTREPRENEUR",
}


def strip_accents(value: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", value)
        if unicodedata.category(c) != "Mn"
    )


def normalize_company_name(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    value = strip_accents(value.upper())
    value = re.sub(r"[^A-Z0-9 ]+", " ", value)
    value = " ".join(value.split())

    tokens = [token for token in value.split() if token not in LEGAL_SUFFIXES]
    if not tokens:
        return value

    return " ".join(tokens)


def normalize_digits(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return re.sub(r"\D", "", value)


def normalize_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return " ".join(value.strip().upper().split())


def normalize_tva(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.upper().replace(" ", "")


def normalize_iban(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.upper().replace(" ", "")


def normalize_bic(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.upper().replace(" ", "")


def parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def matches_regex(value: Optional[str], pattern: str) -> bool:
    return bool(value and re.match(pattern, value))


def luhn_checksum(number: str) -> bool:
    digits = [int(d) for d in number]
    checksum = 0
    parity = len(digits) % 2

    for i, digit in enumerate(digits):
        if i % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0


def is_valid_siren(siren: Optional[str]) -> bool:
    return bool(siren and matches_regex(siren, SIREN_REGEX) and luhn_checksum(siren))


def is_valid_siret(siret: Optional[str]) -> bool:
    return bool(siret and matches_regex(siret, SIRET_REGEX) and luhn_checksum(siret))


def compute_fr_tva_key_from_siren(siren: str) -> str:
    key = (12 + 3 * (int(siren) % 97)) % 97
    return str(key).zfill(2)


def is_valid_fr_tva(tva_number: Optional[str], siren: Optional[str]) -> bool:
    if not tva_number or not siren:
        return False

    tva_number = normalize_tva(tva_number)
    if not matches_regex(tva_number, TVA_FR_REGEX):
        return False

    provided_key = tva_number[2:4]
    embedded_siren = tva_number[4:]
    expected_key = compute_fr_tva_key_from_siren(siren)

    return embedded_siren == siren and provided_key == expected_key


def is_amount_consistent(
    amount_ht: Optional[float],
    amount_tva: Optional[float],
    amount_ttc: Optional[float],
    tolerance: float = 0.05,
) -> bool:
    if amount_ht is None or amount_tva is None or amount_ttc is None:
        return False
    return abs((amount_ht + amount_tva) - amount_ttc) <= tolerance


def is_valid_bic(bic: Optional[str]) -> bool:
    bic = normalize_bic(bic)
    return bool(bic and matches_regex(bic, BIC_REGEX))


def is_valid_iban(iban: Optional[str]) -> bool:
    iban = normalize_iban(iban)
    if not iban or not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", iban):
        return False

    rearranged = iban[4:] + iban[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isalpha():
            numeric += str(ord(ch) - 55)
        else:
            numeric += ch

    return int(numeric) % 97 == 1


def similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0

    a_norm = normalize_company_name(a) or ""
    b_norm = normalize_company_name(b) or ""

    if not a_norm or not b_norm:
        return 0.0

    if a_norm == b_norm:
        return 1.0

    if a_norm in b_norm or b_norm in a_norm:
        return 0.9

    tokens_a = set(a_norm.split())
    tokens_b = set(b_norm.split())

    if tokens_a and tokens_b:
        jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
        seq = SequenceMatcher(None, a_norm, b_norm).ratio()
        return max(seq, jaccard)

    return SequenceMatcher(None, a_norm, b_norm).ratio()
    

def get_supplier_name(doc: DocumentInput) -> Optional[str]:
    if doc.fields.fournisseur and doc.fields.fournisseur.raison_sociale:
        return doc.fields.fournisseur.raison_sociale
    if doc.fields.emetteur and doc.fields.emetteur.raison_sociale:
        return doc.fields.emetteur.raison_sociale
    return doc.fields.supplier_name


def get_primary_siret(doc: DocumentInput) -> Optional[str]:
    for candidate in [
        doc.fields.siret,
        doc.fields.fournisseur.siret if doc.fields.fournisseur else None,
        doc.fields.emetteur.siret if doc.fields.emetteur else None,
        doc.fields.siret_siege,
    ]:
        norm = normalize_digits(candidate)
        if norm and len(norm) == 14:
            return norm

    if doc.fields.siret_ou_siren:
        value = normalize_digits(doc.fields.siret_ou_siren)
        if value and len(value) == 14:
            return value

    return None


def get_primary_siren(doc: DocumentInput) -> Optional[str]:
    for candidate in [
        doc.fields.siren,
        doc.fields.fournisseur.siren if doc.fields.fournisseur else None,
        doc.fields.emetteur.siren if doc.fields.emetteur else None,
    ]:
        norm = normalize_digits(candidate)
        if norm and len(norm) == 9:
            return norm

    siret = get_primary_siret(doc)
    if siret:
        return siret[:9]

    if doc.fields.siret_ou_siren:
        value = normalize_digits(doc.fields.siret_ou_siren)
        if value and len(value) == 9:
            return value

    return None

def get_primary_valid_siret(doc: DocumentInput) -> Optional[str]:
    siret = get_primary_siret(doc)
    if siret and is_valid_siret(siret):
        return siret
    return None


def get_primary_valid_siren(doc: DocumentInput) -> Optional[str]:
    siren = get_primary_siren(doc)
    if siren and is_valid_siren(siren):
        return siren
    return None    


def get_primary_entity_name(doc: DocumentInput) -> Optional[str]:
    candidates = [
        doc.fields.fournisseur.raison_sociale if doc.fields.fournisseur else None,
        doc.fields.emetteur.raison_sociale if doc.fields.emetteur else None,
        doc.fields.supplier_name,
        doc.fields.denomination,
        doc.fields.titulaire,
        doc.fields.titulaire_compte.raison_sociale if doc.fields.titulaire_compte else None,
    ]

    for candidate in candidates:
        normalized = normalize_company_name(candidate)
        if normalized:
            return normalized

    return None


def build_document_groups(batch: BatchInput) -> Dict[str, List[DocumentInput]]:
    groups: Dict[str, List[DocumentInput]] = {}
    group_aliases: Dict[str, str] = {}

    for doc in batch.documents:
        valid_siret = get_primary_valid_siret(doc)
        valid_siren = get_primary_valid_siren(doc)
        primary_name = get_primary_entity_name(doc)

        # priorité : SIRET valide
        if valid_siret:
            key = f"siret:{valid_siret}"
            groups.setdefault(key, []).append(doc)

            if primary_name:
                group_aliases[primary_name] = key
            continue

        # sinon SIREN valide
        if valid_siren:
            key = f"siren:{valid_siren}"
            groups.setdefault(key, []).append(doc)

            if primary_name:
                group_aliases[primary_name] = key
            continue

        # sinon tentative par nom exact 
        if primary_name and primary_name in group_aliases:
            key = group_aliases[primary_name]
            groups.setdefault(key, []).append(doc)
            continue

        # sinon tentative par similarité sur nom
        matched_key = None
        if primary_name:
            for known_name, existing_key in group_aliases.items():
                if similarity(primary_name, known_name) >= 0.85:
                    matched_key = existing_key
                    break

        if matched_key:
            groups.setdefault(matched_key, []).append(doc)
            group_aliases[primary_name] = matched_key
            continue

        # sinon document isolé
        if primary_name:
            key = f"name:{primary_name}"
            groups.setdefault(key, []).append(doc)
            group_aliases[primary_name] = key
        else:
            key = f"document:{doc.document_id}"
            groups.setdefault(key, []).append(doc)

    return groups


def get_critical_fields_by_doc_type(doc_type: str) -> List[str]:
    mapping = {
        "facture": ["numero_facture", "date_facture", "amount_ttc", "siret", "tva_number"],
        "devis": ["numero_devis", "date_devis", "amount_ttc"],
        "attestation": ["date_emission", "date_expiration"],
        "attestation_siret": ["siret", "date_emission", "date_expiration"],
        "attestation_vigilance": ["date_emission", "date_expiration"],
        "attestation_vigilance_urssaf": ["date_emission", "date_expiration"],
        "rib": ["iban", "bic", "titulaire"],
        "extrait_kbis": ["siren", "siret_siege", "denomination"],
    }
    return mapping.get(doc_type, [])


def apparent_vat_rate(
    amount_ht: Optional[float],
    amount_tva: Optional[float],
) -> Optional[float]:
    if amount_ht is None or amount_tva is None:
        return None
    if amount_ht == 0:
        return None
    return amount_tva / amount_ht


def get_candidate_parties_for_insee(doc: DocumentInput) -> List[Tuple[str, Optional[Party]]]:
    return [
        ("fournisseur", doc.fields.fournisseur),
        ("client", doc.fields.client),
        ("emetteur", doc.fields.emetteur),
        ("commanditaire", doc.fields.commanditaire),
        ("titulaire_compte", doc.fields.titulaire_compte),
        ("partie_1", doc.fields.partie_1),
        ("partie_2", doc.fields.partie_2),
    ]


def most_common_name(names: List[str]) -> Optional[str]:
    if not names:
        return None
    return Counter(names).most_common(1)[0][0]