"""
nlp_ocr/ner_extractor.py
═════════════════════════
Extraction des entités nommées et champs métier.

Couche 1 — Regex déterministes (SIRET, TVA, IBAN, BIC, montants, dates, email, tél)
Couche 2 — spaCy NER fr_core_news_md (ORG, PER)

Usage::

    from nlp_ocr.ner_extractor import extract_fields
    from nlp_ocr.schema import DocumentType

    data = extract_fields(text, DocumentType.FACTURE)  # → FactureData
"""
from __future__ import annotations
import re, logging, datetime
from typing import Optional

import dateparser

from nlp_ocr.schema import (
    DocumentType, ExtractionMethod, ExtractedField, EntrepriseInfo,
    FactureData, DevisData, AttestationSiretData,
    AttestationUrssafData, KbisData, RibData,
)

log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# Patterns regex
# ═══════════════════════════════════════════════════════════════════

RE_SIRET   = re.compile(r"(?:siret\s*[:\-]?\s*)?(?<!\d)(\d{3}[\s.\-]?\d{3}[\s.\-]?\d{3}[\s.\-]?\d{5})(?!\d)", re.I)
RE_SIREN   = re.compile(r"(?:siren\s*[:\-]?\s*)(?<!\d)(\d{3}[\s.\-]?\d{3}[\s.\-]?\d{3})(?!\d)", re.I)
RE_TVA     = re.compile(r"\bFR\s?([A-Z0-9]{2})\s?(\d{3})\s?(\d{3})\s?(\d{3})\b", re.I)
RE_IBAN    = re.compile(r"\bFR\d{2}(?:\s?\d{4}){5}\s?\d{3}\b", re.I)
RE_BIC     = re.compile(r"(?:BIC|SWIFT)\s*[:\-]?\s*([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b", re.I)

RE_NUM_FACTURE    = re.compile(r"(?:facture|fact\.?|invoice|fac)\s*[n°#\-:\s]*([A-Z0-9][-/A-Z0-9]{3,20})", re.I)
RE_NUM_DEVIS      = re.compile(r"(?:devis|quotation|quote)\s*[n°#\-:\s]*([A-Z0-9][-/A-Z0-9]{3,20})", re.I)
RE_NUM_ATTESTATION = re.compile(r"n[°o]?\s*(?:d['']\s*)?attestation\s*[:\-]?\s*([A-Z0-9]{5,20})", re.I)

RE_MONTANT_HT  = re.compile(r"(?:sous[\s-]?total|montant|total)\s*h\.?t\.?\s*[:\-]?\s*([\d\s]{1,10}[,.]?\d{0,2})\s*(?:€|EUR|euros?)?", re.I)
RE_MONTANT_TTC = re.compile(r"(?:total|montant)\s*t\.?t\.?c\.?\s*[:\-]?\s*([\d\s]{1,10}[,.]?\d{0,2})\s*(?:€|EUR|euros?)?", re.I)
RE_MONTANT_TVA = re.compile(r"(?:montant|total)?\s*tva\s*[:\-]?\s*([\d\s]{1,10}[,.]?\d{0,2})\s*(?:€|EUR|euros?)?", re.I)
RE_TAUX_TVA    = re.compile(r"tva\s*[:\-]?\s*(\d{1,2}(?:[,.]\d+)?)\s*%", re.I)

RE_DATE_EMISSION = re.compile(
    r"date\s*(?:d['']\s*)?(?:[eé]mission|facture|[eé]dition|document|cr[eé]ation)?\s*[:\-]?\s*"
    r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{4}[/\-\.]\d{2}[/\-\.]\d{2})", re.I)
RE_DATE_ECHEANCE = re.compile(
    r"date\s*(?:d['']\s*)?(?:[eé]ch[eé]ance|expiration|validit[eé]|limite)\s*[:\-]?\s*"
    r"(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}|\d{4}[/\-\.]\d{2}[/\-\.]\d{2})", re.I)
RE_DATE_GENERIC = re.compile(r"\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b")

RE_EMAIL   = re.compile(r"\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b")
RE_TEL     = re.compile(r"(?:t[eé]l\.?|t[eé]l[eé]phone?)?\s*((?:\+33\s?|0033\s?|0)[1-9](?:[\s.\-]?\d{2}){4})", re.I)
RE_CP      = re.compile(r"\b([0-9]{5})\b")
RE_BANQUE  = re.compile(r"\b(BNP\s*Paribas|Cr[eé]dit\s*Agricole|Soci[eé]t[eé]\s*G[eé]n[eé]rale|LCL|Caisse\s*d['']\s*[eÉ]pargne|Banque\s*Populaire|CIC|La\s*Banque\s*Postale|HSBC|Natixis|Cr[eé]dit\s*Mutuel)\b", re.I)
RE_FORME   = re.compile(r"\b(SARL|SAS(?:U)?|SA\b|EURL|SNC|SCI|SC\b|GIE|EIRL|EI\b|MICRO[\s-]ENTREPRISE|AUTO[\s-]?ENTREPRENEUR)\b", re.I)
RE_CAPITAL = re.compile(r"capital\s*(?:social)?\s*[:\-]?\s*([\d\s.,]+\s*(?:€|EUR|euros?)?)", re.I)

# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _first(pat: re.Pattern, text: str, g: int = 1) -> Optional[str]:
    m = pat.search(text)
    return m.group(g).strip() if m else None

def _ef(value: Optional[str], conf: float, method: ExtractionMethod,
        raw: Optional[str] = None) -> ExtractedField:
    if value:
        return ExtractedField(value=value, confidence=conf, method=method, raw_ocr=raw)
    return ExtractedField()

def _norm_siret(s: str) -> str: return re.sub(r"[\s.\-]", "", s)
def _norm_iban(s: str) -> str:  return re.sub(r"\s", "", s.upper())
def _norm_tva(m: re.Match) -> str: return f"FR{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"

def _norm_montant(raw: Optional[str]) -> Optional[str]:
    if not raw: return None
    s = re.sub(r"[€\sEUReuros]", "", raw.strip())
    if re.search(r",\d{2}$", s):
        s = s.replace(".", "").replace(" ", "").replace(",", ".")
    else:
        s = s.replace(",", "").replace(" ", "")
    try: float(s); return s
    except ValueError: return raw.strip()

def _norm_date(raw: Optional[str]) -> Optional[str]:
    if not raw: return None
    p = dateparser.parse(raw, languages=["fr"], settings={"DATE_ORDER": "DMY"})
    return p.date().isoformat() if p else raw.strip()

# ═══════════════════════════════════════════════════════════════════
# spaCy (chargement paresseux)
# ═══════════════════════════════════════════════════════════════════

_nlp = None
def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("fr_core_news_md")
            log.info("spaCy fr_core_news_md chargé")
        except OSError:
            log.warning("fr_core_news_md absent — NER désactivé")
            _nlp = False
    return None if _nlp is False else _nlp

def _ner_orgs(text: str) -> list[str]:
    nlp = _get_nlp()
    if not nlp: return []
    return list({e.text.strip() for e in nlp(text[:5000]).ents if e.label_ == "ORG"})

def _ner_persons(text: str) -> list[str]:
    nlp = _get_nlp()
    if not nlp: return []
    return list({e.text.strip() for e in nlp(text[:5000]).ents if e.label_ == "PER"})

# ═══════════════════════════════════════════════════════════════════
# Bloc EntrepriseInfo (réutilisé dans tous les types)
# ═══════════════════════════════════════════════════════════════════

def _entreprise(text: str, name_hint: Optional[str] = None) -> EntrepriseInfo:
    info = EntrepriseInfo()
    siret_raw = _first(RE_SIRET, text)
    if siret_raw:
        cs = _norm_siret(siret_raw)
        info.siret = _ef(cs,      0.92, ExtractionMethod.REGEX,      siret_raw)
        info.siren = _ef(cs[:9],  0.92, ExtractionMethod.RULE_BASED)
    else:
        sr = _first(RE_SIREN, text)
        if sr: info.siren = _ef(_norm_siret(sr), 0.88, ExtractionMethod.REGEX, sr)

    tva_m = RE_TVA.search(text)
    if tva_m: info.tva_intracom = _ef(_norm_tva(tva_m), 0.93, ExtractionMethod.REGEX, tva_m.group(0))

    iban_r = _first(RE_IBAN, text, 0)
    if iban_r: info.iban = _ef(_norm_iban(iban_r), 0.91, ExtractionMethod.REGEX, iban_r)
    bic_r = _first(RE_BIC, text, 1)
    if bic_r: info.bic = _ef(bic_r.upper(), 0.90, ExtractionMethod.REGEX, bic_r)

    email_r = _first(RE_EMAIL, text)
    if email_r: info.email = _ef(email_r.lower(), 0.95, ExtractionMethod.REGEX)
    tel_r = _first(RE_TEL, text, 1)
    if tel_r: info.telephone = _ef(tel_r, 0.88, ExtractionMethod.REGEX, tel_r)
    cp_r = _first(RE_CP, text)
    if cp_r: info.code_postal = _ef(cp_r, 0.80, ExtractionMethod.REGEX)

    if name_hint:
        info.nom = _ef(name_hint, 0.75, ExtractionMethod.RULE_BASED)
    else:
        orgs = _ner_orgs(text)
        if orgs: info.nom = _ef(orgs[0], 0.65, ExtractionMethod.NER_MODEL)

    return info


def _split(text: str) -> dict[str, str]:
    """Tente de séparer bloc émetteur / destinataire."""
    kw = re.compile(r"\b(destinataire|client|factur[eé]\s*[àa]|adress[eé]\s*[àa])\b", re.I)
    m  = kw.search(text)
    if m: return {"emetteur": text[:m.start()], "destinataire": text[m.start():]}
    mid = len(text) // 2
    return {"emetteur": text[:mid], "destinataire": text[mid:]}

# ═══════════════════════════════════════════════════════════════════
# Extracteurs par type
# ═══════════════════════════════════════════════════════════════════

def _facture(text: str) -> FactureData:
    d = FactureData(); s = _split(text)
    d.numero_facture = _ef(_first(RE_NUM_FACTURE, text), 0.88, ExtractionMethod.REGEX)
    dr = _first(RE_DATE_EMISSION, text)
    d.date_emission  = _ef(_norm_date(dr), 0.85, ExtractionMethod.REGEX, dr)
    er = _first(RE_DATE_ECHEANCE, text)
    d.date_echeance  = _ef(_norm_date(er), 0.85, ExtractionMethod.REGEX, er)
    hr = _first(RE_MONTANT_HT, text)
    d.montant_ht     = _ef(_norm_montant(hr), 0.87, ExtractionMethod.REGEX, hr)
    tr = _first(RE_MONTANT_TTC, text)
    d.montant_ttc    = _ef(_norm_montant(tr), 0.87, ExtractionMethod.REGEX, tr)
    vr = _first(RE_MONTANT_TVA, text)
    d.montant_tva    = _ef(_norm_montant(vr), 0.85, ExtractionMethod.REGEX, vr)
    tx = _first(RE_TAUX_TVA, text)
    d.taux_tva       = _ef(tx, 0.90, ExtractionMethod.REGEX, tx)
    d.emetteur       = _entreprise(s.get("emetteur", text))
    d.destinataire   = _entreprise(s.get("destinataire", text))
    return d


def _devis(text: str) -> DevisData:
    d = DevisData(); s = _split(text)
    d.numero_devis  = _ef(_first(RE_NUM_DEVIS, text), 0.88, ExtractionMethod.REGEX)
    dr = _first(RE_DATE_EMISSION, text)
    d.date_emission = _ef(_norm_date(dr), 0.85, ExtractionMethod.REGEX, dr)
    er = _first(RE_DATE_ECHEANCE, text)
    d.date_validite = _ef(_norm_date(er), 0.85, ExtractionMethod.REGEX, er)
    hr = _first(RE_MONTANT_HT, text)
    d.montant_ht    = _ef(_norm_montant(hr), 0.87, ExtractionMethod.REGEX, hr)
    tr = _first(RE_MONTANT_TTC, text)
    d.montant_ttc   = _ef(_norm_montant(tr), 0.87, ExtractionMethod.REGEX, tr)
    d.emetteur = _entreprise(s.get("emetteur", text))
    d.client   = _entreprise(s.get("destinataire", text))
    return d


def _att_siret(text: str) -> AttestationSiretData:
    d = AttestationSiretData()
    sr = _first(RE_SIRET, text)
    if sr:
        cs = _norm_siret(sr)
        d.siret = _ef(cs,     0.93, ExtractionMethod.REGEX, sr)
        d.siren = _ef(cs[:9], 0.93, ExtractionMethod.RULE_BASED)
    dr = _first(RE_DATE_EMISSION, text)
    d.date_creation = _ef(_norm_date(dr), 0.82, ExtractionMethod.REGEX, dr)
    orgs = _ner_orgs(text)
    if orgs: d.denomination = _ef(orgs[0], 0.65, ExtractionMethod.NER_MODEL)
    return d


def _att_urssaf(text: str) -> AttestationUrssafData:
    d = AttestationUrssafData()
    sr = _first(RE_SIRET, text)
    if sr: d.siret = _ef(_norm_siret(sr), 0.93, ExtractionMethod.REGEX, sr)

    d.numero_attestation = _ef(_first(RE_NUM_ATTESTATION, text), 0.88, ExtractionMethod.REGEX)

    all_dates = list(RE_DATE_GENERIC.finditer(text))
    if all_dates:
        r0 = all_dates[0].group(0)
        d.date_emission = _ef(_norm_date(r0), 0.80, ExtractionMethod.REGEX, r0)
    if len(all_dates) >= 2:
        rl = all_dates[-1].group(0)
        nd = _norm_date(rl)
        d.date_expiration = _ef(nd, 0.82, ExtractionMethod.REGEX, rl)
        if nd:
            try: d.is_expired = datetime.date.fromisoformat(nd) < datetime.date.today()
            except ValueError: pass

    # Fallback : chercher label «expiration»
    if not d.date_expiration.value:
        er = _first(RE_DATE_ECHEANCE, text)
        if er:
            nd = _norm_date(er)
            d.date_expiration = _ef(nd, 0.85, ExtractionMethod.REGEX, er)
            if nd:
                try: d.is_expired = datetime.date.fromisoformat(nd) < datetime.date.today()
                except ValueError: pass

    orgs = _ner_orgs(text)
    if orgs: d.denomination = _ef(orgs[0], 0.65, ExtractionMethod.NER_MODEL)
    return d


def _kbis(text: str) -> KbisData:
    d = KbisData()
    sr = _first(RE_SIREN, text) or (_norm_siret(_first(RE_SIRET, text) or "")[:9] or None)
    if sr: d.siren = _ef(_norm_siret(sr), 0.92, ExtractionMethod.REGEX)
    fm = RE_FORME.search(text)
    if fm: d.forme_juridique = _ef(fm.group(0).upper(), 0.92, ExtractionMethod.REGEX)
    cr = _first(RE_CAPITAL, text)
    d.capital_social = _ef(_norm_montant(cr), 0.88, ExtractionMethod.REGEX, cr)
    dr = _first(RE_DATE_EMISSION, text)
    d.date_immatriculation = _ef(_norm_date(dr), 0.80, ExtractionMethod.REGEX, dr)
    orgs = _ner_orgs(text)
    if orgs: d.denomination = _ef(orgs[0], 0.68, ExtractionMethod.NER_MODEL)
    d.dirigeants = _ner_persons(text)[:5]
    return d


def _rib(text: str) -> RibData:
    d = RibData()
    ir = _first(RE_IBAN, text, 0)
    if ir: d.iban = _ef(_norm_iban(ir), 0.94, ExtractionMethod.REGEX, ir)
    br = _first(RE_BIC, text, 1)
    if br: d.bic = _ef(br.upper(), 0.92, ExtractionMethod.REGEX, br)
    bm = RE_BANQUE.search(text)
    if bm: d.banque = _ef(bm.group(0), 0.91, ExtractionMethod.REGEX)
    d.titulaire = _entreprise(text)
    return d

# ═══════════════════════════════════════════════════════════════════
# Dispatcher public
# ═══════════════════════════════════════════════════════════════════

_EXTRACTORS = {
    DocumentType.FACTURE:            _facture,
    DocumentType.DEVIS:              _devis,
    DocumentType.ATTESTATION_SIRET:  _att_siret,
    DocumentType.ATTESTATION_URSSAF: _att_urssaf,
    DocumentType.KBIS:               _kbis,
    DocumentType.RIB:                _rib,
}

def extract_fields(text: str, doc_type: DocumentType):
    """
    Extrait les champs métier du texte OCR selon le type de document.

    Returns:
        FactureData | DevisData | AttestationSiretData |
        AttestationUrssafData | KbisData | RibData | None
    """
    fn = _EXTRACTORS.get(doc_type)
    if not fn:
        log.warning(f"Pas d'extracteur pour : {doc_type}")
        return None
    return fn(text)
