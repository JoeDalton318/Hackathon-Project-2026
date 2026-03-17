"""
tests/test_pipeline.py — Tests d'intégration (pipeline complet).
Génère de vrais PDFs avec fpdf2, les passe dans extract().
Skip automatiquement si fpdf2 ou pytesseract ne sont pas installés.
"""
import json, pytest
from nlp_ocr.schema import DocumentType


def _deps_ok():
    try:
        from fpdf import FPDF
        import pytesseract
        return True
    except ImportError:
        return False


skip_if_no_deps = pytest.mark.skipif(
    not _deps_ok(), reason="fpdf2 ou pytesseract non installé"
)


@skip_if_no_deps
class TestFacture:
    @pytest.fixture(scope="class")
    def result_and_emetteur(self):
        from scripts.generate_dataset import gen_company, gen_facture_pdf
        from nlp_ocr.pipeline import extract
        em  = gen_company()
        cli = gen_company()
        pdf = gen_facture_pdf(em, cli, falsified=False)
        return extract(pdf, file_name="test_facture.pdf"), em

    def test_classification(self, result_and_emetteur):
        result, _ = result_and_emetteur
        assert result.classification.document_type == DocumentType.FACTURE, (
            f"Attendu FACTURE, obtenu {result.classification.document_type.value} "
            f"(conf={result.classification.confidence:.2f})")

    def test_siret_extrait(self, result_and_emetteur):
        result, _ = result_and_emetteur
        assert result.facture is not None
        siret = result.facture.emetteur.siret
        assert siret.value is not None, "SIRET non extrait"
        assert siret.confidence > 0.5

    def test_montant_ttc(self, result_and_emetteur):
        result, _ = result_and_emetteur
        assert result.facture is not None
        assert result.facture.montant_ttc.value is not None, "Montant TTC non extrait"

    def test_confidence_globale(self, result_and_emetteur):
        result, _ = result_and_emetteur
        assert result.overall_confidence > 0.3, (
            f"Confiance trop faible : {result.overall_confidence}")

    def test_serialisation_json(self, result_and_emetteur):
        result, _ = result_and_emetteur
        parsed = json.loads(result.model_dump_json())
        assert "document_id"    in parsed
        assert "classification" in parsed
        assert "facture"        in parsed
        assert parsed["classification"]["document_type"] == "facture"


@skip_if_no_deps
class TestUrssaf:
    @pytest.fixture(scope="class")
    def valid_result(self):
        from scripts.generate_dataset import gen_company, gen_urssaf_pdf
        from nlp_ocr.pipeline import extract
        co = gen_company()
        return extract(gen_urssaf_pdf(co, expired=False), file_name="urssaf_ok.pdf")

    @pytest.fixture(scope="class")
    def expired_result(self):
        from scripts.generate_dataset import gen_company, gen_urssaf_pdf
        from nlp_ocr.pipeline import extract
        co = gen_company()
        return extract(gen_urssaf_pdf(co, expired=True), file_name="urssaf_exp.pdf")

    def test_type_urssaf(self, valid_result):
        assert valid_result.classification.document_type == DocumentType.ATTESTATION_URSSAF

    def test_valide_pas_de_warning_expiration(self, valid_result):
        warns = [w for w in valid_result.extraction_warnings if "EXPIR" in w.upper()]
        assert len(warns) == 0, f"Faux positif expiration : {warns}"

    def test_expire_detecte(self, expired_result):
        if (att := expired_result.attestation_urssaf) and att.date_expiration.value:
            assert att.is_expired is True, "Attestation expirée non détectée"


@skip_if_no_deps
class TestRib:
    @pytest.fixture(scope="class")
    def result(self):
        from scripts.generate_dataset import gen_company, gen_rib_pdf
        from nlp_ocr.pipeline import extract
        co = gen_company()
        return extract(gen_rib_pdf(co), file_name="rib.pdf")

    def test_type_rib(self, result):
        assert result.classification.document_type == DocumentType.RIB

    def test_iban_extrait(self, result):
        assert result.rib is not None
        v = result.rib.iban.value
        assert v is not None and " " not in v

    def test_bic_extrait(self, result):
        assert result.rib is not None
        assert result.rib.bic.value is not None


@skip_if_no_deps
class TestFalsified:
    """Vérifie que la validation détecte les SIRET corrompus."""
    @pytest.fixture(scope="class")
    def result(self):
        from scripts.generate_dataset import gen_company, gen_facture_pdf
        from nlp_ocr.pipeline import extract
        em  = gen_company()
        cli = gen_company()
        pdf = gen_facture_pdf(em, cli, falsified=True)
        return extract(pdf, file_name="facture_falsified.pdf")

    def test_warning_siret_invalide(self, result):
        # Le SIRET corrompu doit générer un avertissement de validation
        siret_warns = [w for w in result.extraction_warnings if "siret" in w.lower()]
        assert len(siret_warns) > 0, (
            f"SIRET falsifié non signalé. Warnings: {result.extraction_warnings}")
