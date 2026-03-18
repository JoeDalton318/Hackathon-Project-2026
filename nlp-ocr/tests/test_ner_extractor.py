"""tests/test_ner_extractor.py — Tests d'extraction NER."""
import pytest
from nlp_ocr.ner_extractor import (
    extract_fields,
    _norm_montant, _norm_date, _norm_iban, _norm_siret,
)
from nlp_ocr.schema import DocumentType, ExtractionMethod


class TestFacture:
    @pytest.fixture(autouse=True)
    def setup(self, text_facture):
        self.d = extract_fields(text_facture, DocumentType.FACTURE)

    def test_numero(self):
        assert self.d.numero_facture.value is not None
        assert "FAC-2024-0042" in (self.d.numero_facture.value or "")

    def test_date_emission(self):
        assert self.d.date_emission.value == "2024-03-15"

    def test_date_echeance(self):
        assert self.d.date_echeance.value is not None

    def test_montant_ht(self):
        assert self.d.montant_ht.value is not None

    def test_montant_ttc(self):
        assert self.d.montant_ttc.value is not None

    def test_taux_tva(self):
        assert self.d.taux_tva.value == "20"

    def test_siret_emetteur(self):
        assert self.d.emetteur.siret.value is not None
        assert self.d.emetteur.siret.confidence > 0.5

    def test_methode_regex(self):
        assert self.d.emetteur.siret.method == ExtractionMethod.REGEX

    def test_iban_normalise(self):
        v = self.d.emetteur.iban.value
        assert v is not None and " " not in v

    def test_email(self):
        v = self.d.emetteur.email.value
        assert v is not None and "@" in v


class TestUrssafValide:
    @pytest.fixture(autouse=True)
    def setup(self, text_urssaf_valid):
        self.d = extract_fields(text_urssaf_valid, DocumentType.ATTESTATION_URSSAF)

    def test_siret(self):
        assert self.d.siret.value is not None

    def test_num_attestation(self):
        assert self.d.numero_attestation.value is not None

    def test_dates(self):
        assert self.d.date_emission.value is not None
        assert self.d.date_expiration.value is not None

    def test_non_expire(self):
        # fixture avec date 2099
        assert self.d.is_expired is False


class TestUrssafExpire:
    @pytest.fixture(autouse=True)
    def setup(self, text_urssaf_expired):
        self.d = extract_fields(text_urssaf_expired, DocumentType.ATTESTATION_URSSAF)

    def test_expire_detecte(self):
        assert self.d.is_expired is True


class TestRib:
    @pytest.fixture(autouse=True)
    def setup(self, text_rib):
        self.d = extract_fields(text_rib, DocumentType.RIB)

    def test_iban(self):
        v = self.d.iban.value
        assert v is not None and " " not in v and v.startswith("FR76")

    def test_bic(self):
        assert self.d.bic.value == "BNPAFRPP"

    def test_banque(self):
        assert self.d.banque.value is not None
        assert "BNP" in (self.d.banque.value or "").upper()


class TestKbis:
    @pytest.fixture(autouse=True)
    def setup(self, text_kbis):
        self.d = extract_fields(text_kbis, DocumentType.KBIS)

    def test_forme_juridique(self):
        assert self.d.forme_juridique.value == "SARL"

    def test_capital(self):
        assert self.d.capital_social.value is not None

    def test_date_immatriculation(self):
        assert self.d.date_immatriculation.value is not None


class TestNormalisations:
    def test_montant_fr(self):
        assert _norm_montant("1 250,50 €") == "1250.50"

    def test_montant_point(self):
        assert _norm_montant("1.250,50") == "1250.50"

    def test_date_slash(self):
        assert _norm_date("15/03/2024") == "2024-03-15"

    def test_date_tiret(self):
        assert _norm_date("15-03-2024") == "2024-03-15"

    def test_date_iso(self):
        assert _norm_date("2024-03-15") == "2024-03-15"

    def test_iban_espaces(self):
        r = _norm_iban("FR76 3000 6000 01 12345678 189")
        assert " " not in r and r.startswith("FR76")

    def test_siret_espaces(self):
        r = _norm_siret("832 456 789 01234")
        assert " " not in r and len(r) == 14
