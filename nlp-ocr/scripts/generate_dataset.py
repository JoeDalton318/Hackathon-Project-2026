"""
scripts/generate_dataset.py
════════════════════════════
Générateur de dataset synthétique de documents administratifs français.

Usage::

    python scripts/generate_dataset.py --output ./dataset --count 60 --seed 42

Produit dans ./dataset/ :
  pdfs/    → PDF factures, URSSAF, RIBs (légitimes + falsifiés + expirés)
  images/  → conversions dégradées (flou, rotation, bruit, smartphone)
  manifest.json → ground truth pour l'évaluation
"""
from __future__ import annotations
import argparse, json, logging, random, sys
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

# Ajout du répertoire parent au path pour pouvoir importer nlp_ocr
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
import numpy as np
from faker import Faker
from fpdf import FPDF
from PIL import Image, ImageFilter

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

fake = Faker("fr_FR")

BINOMES = [
    "Alioune Diop", "Yasmine Benali", "Théo Marchais",
    "Camille Leroy", "Romain Dupont", "Inès Ouali",
]
FORMES_JURIDIQUES = ["SARL", "SAS", "SASU", "SA", "EURL", "SNC"]
TVA_TAUX          = [20.0, 10.0, 5.5, 2.1]


# ── Génération de données d'entreprise ──────────────────────────────────────

def _luhn_ok(number: str) -> bool:
    total = 0
    for i, d in enumerate(reversed(number)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9: n -= 9
        total += n
    return total % 10 == 0


def gen_siret() -> str:
    while True:
        base = "".join(str(random.randint(0, 9)) for _ in range(13))
        for check in range(10):
            if _luhn_ok(base + str(check)):
                return base + str(check)


def gen_tva(siren: str) -> str:
    key = (12 + 3 * (int(siren) % 97)) % 97
    return f"FR{key:02d}{siren}"


def gen_iban(siret: str) -> str:
    return f"FR76 30003 {random.randint(10000,99999)} {siret[:5]} {siret[5:11]} 00"


def gen_company(binome: Optional[str] = None) -> dict:
    forme = random.choice(FORMES_JURIDIQUES)
    name  = (f"{binome.split()[1].upper()} Consulting {forme}" if binome
             else f"{fake.last_name().upper()} {random.choice(['Services','Solutions','Conseil'])} {forme}")
    siret = gen_siret()
    siren = siret[:9]
    return {"name": name, "siret": siret, "siren": siren, "tva": gen_tva(siren),
            "address": fake.street_address(), "zip": fake.postcode(), "city": fake.city(),
            "phone": fake.phone_number(), "email": f"contact@{name.split()[0].lower()}.fr",
            "iban": gen_iban(siret), "bic": "BNPAFRPP",
            "forme_juridique": forme, "capital": random.choice([1000,5000,10000,50000,100000])}


def _date_past(days: int = 365) -> date:
    return date.today() - timedelta(days=random.randint(1, days))


# ── Générateurs PDF ──────────────────────────────────────────────────────────

class _PDF(FPDF):
    def header(self): pass
    def footer(self): pass


def _company_block(pdf: _PDF, c: dict, x: float, y: float):
    pdf.set_xy(x, y)
    pdf.set_font("Helvetica", "B", 11); pdf.cell(0, 6, c["name"], ln=True)
    pdf.set_font("Helvetica", "", 9)
    for line in [c["address"], f"{c['zip']} {c['city']}",
                 f"SIRET : {c['siret']}", f"TVA : {c['tva']}",
                 f"Tél : {c['phone']}", f"Email : {c['email']}"]:
        pdf.set_x(x); pdf.cell(0, 5, line, ln=True)


def gen_facture_pdf(emetteur: dict, client: dict, falsified: bool = False) -> bytes:
    pdf   = _PDF(); pdf.add_page()
    taux  = random.choice(TVA_TAUX)
    num   = f"FAC-{date.today().year}-{random.randint(1000,9999)}"
    d_em  = _date_past(180); d_ec = d_em + timedelta(days=30)

    pdf.set_font("Helvetica", "B", 18); pdf.cell(0, 10, "FACTURE", align="C", ln=True); pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 6, f"N° : {num}"); pdf.cell(0, 6, f"Date d'émission : {d_em.strftime('%d/%m/%Y')}", ln=True)
    pdf.cell(95, 6, "");            pdf.cell(0, 6, f"Date d'échéance : {d_ec.strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(4)

    y0 = pdf.get_y()
    _company_block(pdf, emetteur, 10, y0)
    _company_block(pdf, client, 110, y0)
    pdf.set_y(y0 + 52); pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10); pdf.set_fill_color(220, 220, 220)
    for lbl, w in [("Désignation", 90), ("Qté", 20), ("P.U. HT", 30), ("Total HT", 30)]:
        pdf.cell(w, 8, lbl, border=1, fill=True, align="C" if w < 90 else "L")
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    total_ht = 0.0
    for _ in range(random.randint(2, 4)):
        desc = fake.bs().capitalize()[:48]; qty = random.randint(1, 8)
        pu   = round(random.uniform(100, 3000), 2); lht = round(qty * pu, 2); total_ht += lht
        pdf.cell(90, 7, desc, border=1); pdf.cell(20, 7, str(qty), border=1, align="C")
        pdf.cell(30, 7, f"{pu:,.2f} EUR".replace(",", " "), border=1, align="R")
        pdf.cell(30, 7, f"{lht:,.2f} EUR".replace(",", " "), border=1, align="R"); pdf.ln()

    total_tva = round(total_ht * taux / 100, 2); total_ttc = round(total_ht + total_tva, 2)
    display_siret = emetteur["siret"]
    if falsified:
        chars = list(display_siret); chars[3], chars[7] = chars[7], chars[3]
        display_siret = "".join(chars)

    pdf.ln(4); pdf.set_font("Helvetica", "", 10)
    for lbl, val in [(f"Montant HT", f"{total_ht:,.2f} EUR".replace(",", " ")),
                     (f"TVA ({taux}%)", f"{total_tva:,.2f} EUR".replace(",", " "))]:
        pdf.cell(140, 7, ""); pdf.cell(0, 7, f"{lbl} : {val}", ln=True)
    pdf.set_font("Helvetica", "B", 11); pdf.cell(140, 8, "")
    pdf.cell(0, 8, f"Total TTC : {total_ttc:,.2f} EUR".replace(",", " "), ln=True)

    pdf.ln(8); pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, "Coordonnées bancaires :", ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"IBAN : {emetteur['iban']}", ln=True)
    pdf.cell(0, 5, f"BIC  : {emetteur['bic']}",  ln=True)
    pdf.cell(0, 5, f"SIRET : {display_siret}",    ln=True)
    return bytes(pdf.output())


def gen_urssaf_pdf(company: dict, expired: bool = False) -> bytes:
    pdf  = _PDF(); pdf.add_page()
    d_em = _date_past(60)
    d_exp = (d_em - timedelta(days=random.randint(30, 180))
             if expired else d_em + timedelta(days=180))
    num  = f"ATT{random.randint(100000, 999999)}"

    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "ATTESTATION DE VIGILANCE", align="C", ln=True)
    pdf.set_font("Helvetica", "B", 11); pdf.cell(0, 8, "URSSAF Île-de-France", align="C", ln=True); pdf.ln(6)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"N° d'attestation : {num}", ln=True); pdf.ln(2)
    pdf.cell(0, 6, "Cette attestation certifie que l'entreprise :", ln=True); pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10); pdf.cell(0, 6, company["name"], ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"SIRET : {company['siret']}", ln=True)
    pdf.cell(0, 6, f"{company['address']}, {company['zip']} {company['city']}", ln=True); pdf.ln(4)
    pdf.multi_cell(0, 6, "est à jour de ses obligations de déclaration et de paiement auprès de l'URSSAF.")
    pdf.ln(4)
    pdf.cell(0, 6, f"Date d'émission   : {d_em.strftime('%d/%m/%Y')}",  ln=True)
    pdf.cell(0, 6, f"Date d'expiration : {d_exp.strftime('%d/%m/%Y')}", ln=True); pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, f"Document valide du {d_em.strftime('%d/%m/%Y')} au {d_exp.strftime('%d/%m/%Y')}. "
                  "Vérifiable sur net-entreprises.fr")
    return bytes(pdf.output())


def gen_rib_pdf(company: dict) -> bytes:
    pdf = _PDF(); pdf.add_page()
    pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 10, "RELEVÉ D'IDENTITÉ BANCAIRE (RIB)", align="C", ln=True); pdf.ln(6)
    pdf.set_font("Helvetica", "", 10)
    for line in [f"Titulaire : {company['name']}", f"SIRET : {company['siret']}",
                 f"Adresse : {company['address']}, {company['zip']} {company['city']}",
                 "", "Domiciliation : BNP Paribas",
                 f"IBAN : {company['iban']}", f"BIC  : {company['bic']}"]:
        pdf.cell(0, 7, line, ln=True)
    return bytes(pdf.output())


# ── Dégradation d'image ──────────────────────────────────────────────────────

def degrade(img: np.ndarray, mode: str) -> np.ndarray:
    if mode == "blur":
        return np.array(Image.fromarray(img).filter(ImageFilter.GaussianBlur(random.uniform(1.5, 4.0))))
    if mode == "rotate":
        a = random.uniform(-15, 15); h, w = img.shape[:2]
        return cv2.warpAffine(img, cv2.getRotationMatrix2D((w/2, h/2), a, 1.0), (w, h), borderValue=255)
    if mode == "noise":
        return cv2.add(img, np.random.randint(0, 50, img.shape, dtype=np.uint8))
    if mode == "smartphone":
        out = degrade(degrade(degrade(img, "rotate"), "blur"), "noise")
        h, w = out.shape[:2]
        return cv2.resize(cv2.resize(out, (w//2, h//2)), (w, h), interpolation=cv2.INTER_LINEAR)
    return img


def pdf_to_image(pdf_bytes: bytes) -> np.ndarray:
    try:
        import fitz
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        img = np.frombytes("uint8", [pix.width, pix.height, 3], pix.samples)
        doc.close(); return img
    except Exception:
        return np.ones((800, 600, 3), dtype=np.uint8) * 255


# ── Assemblage du dataset ────────────────────────────────────────────────────

def build_dataset(output_dir: Path, count: int = 60) -> list[dict]:
    (output_dir / "pdfs").mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(parents=True, exist_ok=True)
    manifest = []

    def _pdf(data, name, meta):
        (output_dir / "pdfs" / name).write_bytes(data)
        manifest.append({**meta, "file": f"pdfs/{name}", "format": "pdf"})

    def _img(arr, name, meta, mode=None):
        if mode: arr = degrade(arr, mode)
        cv2.imwrite(str(output_dir / "images" / name), arr)
        manifest.append({**meta, "file": f"images/{name}", "format": "image", "degradation": mode})

    for i in range(count):
        idx      = f"{i:04d}"
        binome   = BINOMES[i % len(BINOMES)]
        emetteur = gen_company(binome)
        client   = gen_company()

        # Facture légitime + image propre + smartphone
        pdf = gen_facture_pdf(emetteur, client, falsified=False)
        _pdf(pdf, f"facture_{idx}.pdf",
             {"type": "facture", "label": "legitimate",
              "siret_emetteur": emetteur["siret"], "siret_client": client["siret"]})
        img = pdf_to_image(pdf)
        _img(img, f"facture_{idx}_clean.jpg",      {"type": "facture", "label": "clean"})
        _img(img, f"facture_{idx}_smartphone.jpg",  {"type": "facture", "label": "degraded"}, "smartphone")

        # Facture falsifiée (1/3)
        if i % 3 == 0:
            fls = gen_facture_pdf(emetteur, client, falsified=True)
            _pdf(fls, f"facture_{idx}_falsified.pdf",
                 {"type": "facture", "label": "falsified",
                  "siret_emetteur": emetteur["siret"], "expected_siret_invalid": True})

        # URSSAF valide
        _pdf(gen_urssaf_pdf(emetteur, expired=False), f"urssaf_{idx}_valid.pdf",
             {"type": "attestation_vigilance_urssaf", "label": "valid", "siret": emetteur["siret"]})

        # URSSAF expirée (1/4)
        if i % 4 == 0:
            _pdf(gen_urssaf_pdf(emetteur, expired=True), f"urssaf_{idx}_expired.pdf",
                 {"type": "attestation_vigilance_urssaf", "label": "expired",
                  "siret": emetteur["siret"], "expected_expired": True})

        # RIB
        _pdf(gen_rib_pdf(emetteur), f"rib_{idx}.pdf",
             {"type": "rib", "label": "legitimate",
              "iban": emetteur["iban"], "siret": emetteur["siret"]})

        if i % 10 == 0:
            log.info(f"  {i}/{count} sets générés")

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info(f"Dataset : {len(manifest)} documents → {output_dir}")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="./dataset")
    parser.add_argument("--count",  type=int, default=60)
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed); Faker.seed(args.seed)
    build_dataset(Path(args.output), count=args.count)
