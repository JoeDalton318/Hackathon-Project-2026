"""
nlp_ocr/validator.py
═════════════════════
Validation métier des champs extraits.

Règles :
  SIRET/SIREN  → algorithme de Luhn (INSEE)
  TVA          → clé = (12 + 3 × SIREN % 97) % 97
  IBAN FR      → checksum ISO 13616 (mod 97 == 1)
  Date expir.  → < aujourd'hui
  Cohérence    → émission ≤ échéance · HT + TVA ≈ TTC (±1€)
  SIRET croisé → même SIRET sur deux documents

Usage::

    from nlp_ocr.validator import validate_siret, validate_facture
    r = validate_siret("83245678901230")
    print(r.is_valid, r.reason)
"""
from __future__ import annotations
import re, logging, datetime
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class FieldValidation:
    field_name:          str
    value:               Optional[str]
    is_valid:            bool
    confidence_boost:    float = 0.0
    confidence_penalty:  float = 0.0
    reason:              str   = ""


@dataclass
class ValidationReport:
    checks:        list[FieldValidation] = field(default_factory=list)
    warnings:      list[str]             = field(default_factory=list)
    errors:        list[str]             = field(default_factory=list)
    overall_valid: bool                  = True

    def add(self, check: FieldValidation):
        self.checks.append(check)
        if not check.is_valid:
            self.overall_valid = False
            msg = f"[{check.field_name}] {check.reason}"
            (self.errors if check.confidence_penalty > 0.25 else self.warnings).append(msg)

    def summary(self) -> str:
        ok = sum(1 for c in self.checks if c.is_valid)
        return f"{ok}/{len(self.checks)} OK"


# ── Luhn ──────────────────────────────────────────────────────────────────────

def _luhn(number: str) -> int:
    total = 0
    for i, d in enumerate(reversed(number)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9: n -= 9
        total += n
    return total

# ── Validateurs atomiques ─────────────────────────────────────────────────────

def validate_siret(siret: Optional[str]) -> FieldValidation:
    """SIRET : 14 chiffres, checksum Luhn."""
    if not siret: return FieldValidation("siret", siret, False, reason="absent")
    clean = re.sub(r"\s", "", siret)
    if not clean.isdigit():
        return FieldValidation("siret", siret, False, confidence_penalty=0.5,
                               reason=f"non-numérique : '{clean}'")
    if len(clean) != 14:
        return FieldValidation("siret", siret, False, confidence_penalty=0.4,
                               reason=f"longueur {len(clean)} ≠ 14")
    valid = (_luhn(clean) % 10 == 0)
    return FieldValidation("siret", siret, is_valid=valid,
                           confidence_boost=0.05 if valid else 0.0,
                           confidence_penalty=0.35 if not valid else 0.0,
                           reason="" if valid else f"Luhn échoue")


def validate_siren(siren: Optional[str]) -> FieldValidation:
    """SIREN : 9 chiffres, checksum Luhn."""
    if not siren: return FieldValidation("siren", siren, False, reason="absent")
    clean = re.sub(r"\s", "", siren)
    if not clean.isdigit() or len(clean) != 9:
        return FieldValidation("siren", siren, False, confidence_penalty=0.3,
                               reason=f"longueur {len(clean)} ≠ 9 ou non-numérique")
    valid = (_luhn(clean) % 10 == 0)
    return FieldValidation("siren", siren, is_valid=valid,
                           confidence_boost=0.05 if valid else 0.0,
                           confidence_penalty=0.30 if not valid else 0.0,
                           reason="" if valid else "Luhn échoue")


def validate_tva(tva: Optional[str], siren: Optional[str] = None) -> FieldValidation:
    """TVA FR : format + cohérence avec SIREN si fourni."""
    if not tva: return FieldValidation("tva_intracom", tva, False, reason="absent")
    clean = re.sub(r"\s", "", tva.upper())
    m     = re.match(r"^FR([A-Z0-9]{2})(\d{9})$", clean)
    if not m:
        return FieldValidation("tva_intracom", tva, False, confidence_penalty=0.30,
                               reason=f"format invalide : {clean}")
    key_ext, siren_ext = m.group(1), m.group(2)
    if siren and siren.isdigit() and len(siren) == 9:
        if siren_ext != siren:
            return FieldValidation("tva_intracom", tva, False, confidence_penalty=0.40,
                                   reason=f"SIREN TVA ({siren_ext}) ≠ SIREN doc ({siren})")
        expected = f"{(12 + 3 * (int(siren) % 97)) % 97:02d}"
        if key_ext != expected:
            return FieldValidation("tva_intracom", tva, False, confidence_penalty=0.35,
                                   reason=f"clé TVA attendue {expected}, reçue {key_ext}")
        return FieldValidation("tva_intracom", tva, True, confidence_boost=0.06)
    return FieldValidation("tva_intracom", tva, True, confidence_boost=0.02,
                           reason="format OK (SIREN absent pour vérif. croisée)")


def validate_iban(iban: Optional[str]) -> FieldValidation:
    """IBAN FR : format + ISO 13616 (mod 97 == 1)."""
    if not iban: return FieldValidation("iban", iban, False, reason="absent")
    clean = re.sub(r"\s", "", iban.upper())
    if not re.match(r"^FR\d{25}$", clean):
        return FieldValidation("iban", iban, False, confidence_penalty=0.30,
                               reason=f"format invalide : {clean}")
    rearr   = clean[4:] + clean[:4]
    numeric = "".join(str(ord(c) - 55) if c.isalpha() else c for c in rearr)
    valid   = int(numeric) % 97 == 1
    return FieldValidation("iban", iban, is_valid=valid,
                           confidence_boost=0.05 if valid else 0.0,
                           confidence_penalty=0.40 if not valid else 0.0,
                           reason="" if valid else "checksum ISO 13616 échoue")


def validate_date_expiration(date_iso: Optional[str],
                              field_name: str = "date_expiration") -> FieldValidation:
    if not date_iso: return FieldValidation(field_name, date_iso, False, reason="absent")
    try:
        exp   = datetime.date.fromisoformat(date_iso)
        valid = exp >= datetime.date.today()
        return FieldValidation(field_name, date_iso, is_valid=valid,
                               reason="" if valid else f"EXPIRÉE depuis {date_iso}")
    except ValueError:
        return FieldValidation(field_name, date_iso, False, confidence_penalty=0.10,
                               reason=f"date non parseable : {date_iso}")


def validate_date_coherence(d_em: Optional[str], d_ec: Optional[str]) -> FieldValidation:
    if not d_em or not d_ec:
        return FieldValidation("date_coherence", None, True, reason="date absente, ignoré")
    try:
        valid = datetime.date.fromisoformat(d_em) <= datetime.date.fromisoformat(d_ec)
        return FieldValidation("date_coherence", f"{d_em}→{d_ec}", is_valid=valid,
                               confidence_penalty=0.25 if not valid else 0.0,
                               reason="" if valid else f"émission ({d_em}) > échéance ({d_ec})")
    except ValueError:
        return FieldValidation("date_coherence", None, True, reason="dates non parseable")


def validate_montants(ht: Optional[str], tva: Optional[str],
                      ttc: Optional[str]) -> FieldValidation:
    """HT + TVA ≈ TTC avec tolérance 1 €."""
    if not all([ht, tva, ttc]):
        return FieldValidation("montants_coherence", None, True, reason="montants incomplets")
    try:
        v_ht  = float(str(ht).replace(",", "."))
        v_tva = float(str(tva).replace(",", "."))
        v_ttc = float(str(ttc).replace(",", "."))
        diff  = abs(v_ht + v_tva - v_ttc)
        valid = diff <= 1.0
        return FieldValidation(
            "montants_coherence", f"HT={ht}+TVA={tva}={v_ht+v_tva:.2f} (TTC={ttc})",
            is_valid=valid, confidence_penalty=0.20 if not valid else 0.0,
            reason="" if valid else f"diff={diff:.2f}€")
    except (ValueError, TypeError):
        return FieldValidation("montants_coherence", None, True, reason="non-numérique, ignoré")


def validate_siret_cross(siret_a: Optional[str], label_a: str,
                         siret_b: Optional[str], label_b: str) -> FieldValidation:
    if not siret_a or not siret_b:
        return FieldValidation("siret_cross", None, True, reason="SIRET absent, ignoré")
    ca, cb = re.sub(r"\s", "", siret_a), re.sub(r"\s", "", siret_b)
    valid  = ca == cb
    return FieldValidation("siret_cross", f"{label_a}={ca} vs {label_b}={cb}",
                           is_valid=valid, confidence_penalty=0.50 if not valid else 0.0,
                           reason="" if valid else f"SIRET incohérent : {ca} ≠ {cb}")

# ── Validateurs de haut niveau ────────────────────────────────────────────────

def validate_facture(data) -> ValidationReport:
    r = ValidationReport()
    r.add(validate_siret(data.emetteur.siret.value))
    r.add(validate_tva(data.emetteur.tva_intracom.value, data.emetteur.siren.value))
    if data.emetteur.iban.value: r.add(validate_iban(data.emetteur.iban.value))
    r.add(validate_montants(data.montant_ht.value, data.montant_tva.value, data.montant_ttc.value))
    r.add(validate_date_coherence(data.date_emission.value, data.date_echeance.value))
    return r

def validate_attestation_urssaf(data) -> ValidationReport:
    r = ValidationReport()
    r.add(validate_siret(data.siret.value))
    r.add(validate_date_expiration(data.date_expiration.value))
    if data.date_emission.value and data.date_expiration.value:
        r.add(validate_date_coherence(data.date_emission.value, data.date_expiration.value))
    return r

def validate_rib(data) -> ValidationReport:
    r = ValidationReport(); r.add(validate_iban(data.iban.value)); return r

def validate_kbis(data) -> ValidationReport:
    r = ValidationReport(); r.add(validate_siren(data.siren.value)); return r