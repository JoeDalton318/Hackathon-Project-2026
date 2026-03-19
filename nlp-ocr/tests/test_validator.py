"""tests/test_validator.py — Tests de validation métier."""
import pytest
from nlp_ocr.validator import (
    validate_siret, validate_siren, validate_tva,
    validate_iban, validate_date_expiration,
    validate_date_coherence, validate_montants, validate_siret_cross,
)


class TestSiret:
    def test_valide(self, valid_siret):
        r = validate_siret(valid_siret)
        assert r.is_valid, r.reason

    def test_avec_espaces(self, valid_siret):
        s = f"{valid_siret[:3]} {valid_siret[3:6]} {valid_siret[6:9]} {valid_siret[9:]}"
        assert validate_siret(s).is_valid

    def test_mauvaise_longueur(self):
        assert not validate_siret("12345678").is_valid

    def test_luhn_echoue(self):
        r = validate_siret("12345678901234")
        assert not r.is_valid
        assert r.confidence_penalty > 0

    def test_absent(self):
        assert not validate_siret(None).is_valid

    def test_non_numerique(self):
        assert not validate_siret("1234567890ABCD").is_valid


class TestTva:
    def test_coherente(self, valid_siret):
        from scripts.generate_dataset import gen_tva
        siren = valid_siret[:9]
        r = validate_tva(gen_tva(siren), siren)
        assert r.is_valid

    def test_siren_mismatch(self):
        assert not validate_tva("FR12832456789", "999999999").is_valid

    def test_format_invalide(self):
        assert not validate_tva("INVALID").is_valid

    def test_sans_siren(self):
        # Format OK, pas de SIREN → valid format-only
        assert validate_tva("FR12832456789").is_valid


class TestIban:
    def test_valide(self):
        assert validate_iban("FR7630006000011234567890189").is_valid

    def test_avec_espaces(self):
        assert validate_iban("FR76 3000 6000 0112 3456 7890 189").is_valid

    def test_checksum_faux(self):
        assert not validate_iban("FR0000000000000000000000000").is_valid

    def test_mauvais_pays(self):
        assert not validate_iban("DE89370400440532013000").is_valid

    def test_absent(self):
        assert not validate_iban(None).is_valid


class TestDates:
    def test_future(self):
        assert validate_date_expiration("2099-12-31").is_valid

    def test_expiree(self):
        r = validate_date_expiration("2020-01-01")
        assert not r.is_valid
        assert "EXPIRÉE" in r.reason

    def test_absente(self):
        assert not validate_date_expiration(None).is_valid

    def test_coherence_ok(self):
        assert validate_date_coherence("2024-01-01", "2024-12-31").is_valid

    def test_coherence_ko(self):
        assert not validate_date_coherence("2024-12-31", "2024-01-01").is_valid

    def test_coherence_date_absente(self):
        assert validate_date_coherence(None, "2024-12-31").is_valid


class TestMontants:
    def test_coherents(self):
        assert validate_montants("1000.00", "200.00", "1200.00").is_valid

    def test_incoherents(self):
        assert not validate_montants("1000.00", "200.00", "9999.00").is_valid

    def test_tolerance_1_euro(self):
        assert validate_montants("1000.00", "200.00", "1200.50").is_valid

    def test_incomplet(self):
        assert validate_montants("1000.00", None, "1200.00").is_valid


class TestCross:
    def test_memes_siret(self, valid_siret):
        assert validate_siret_cross(valid_siret, "fac", valid_siret, "urssaf").is_valid

    def test_siret_differents(self, valid_siret):
        from scripts.generate_dataset import gen_siret
        autre = gen_siret()
        r = validate_siret_cross(valid_siret, "fac", autre, "urssaf")
        assert not r.is_valid
        assert r.confidence_penalty >= 0.5

    def test_absent(self, valid_siret):
        assert validate_siret_cross(None, "fac", valid_siret, "urssaf").is_valid
