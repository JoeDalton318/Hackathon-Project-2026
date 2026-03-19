"""tests/test_classifier.py — Tests de classification."""
import pytest
from nlp_ocr.classifier import classify_document
from nlp_ocr.schema import DocumentType


class TestClassifier:
    def test_facture(self, text_facture):
        r = classify_document(text_facture)
        assert r.document_type == DocumentType.FACTURE
        assert r.confidence > 0.3

    def test_urssaf(self, text_urssaf_valid):
        assert classify_document(text_urssaf_valid).document_type == DocumentType.ATTESTATION_URSSAF

    def test_rib(self, text_rib):
        assert classify_document(text_rib).document_type == DocumentType.RIB

    def test_kbis(self, text_kbis):
        assert classify_document(text_kbis).document_type == DocumentType.KBIS

    def test_devis(self):
        text = "DEVIS N° DEV-2024-099\nProposition commerciale valable jusqu'au 30/04/2024\nDate de validité : 30/04/2024\nMontant HT : 5 000,00 €"
        assert classify_document(text).document_type == DocumentType.DEVIS

    def test_texte_vide(self):
        r = classify_document("")
        assert r.document_type == DocumentType.INCONNU
        assert r.confidence == 0.0

    def test_scores_somment_a_un(self, text_facture):
        r = classify_document(text_facture)
        assert abs(sum(r.scores.values()) - 1.0) < 0.01

    def test_tous_types_presents(self, text_facture):
        r = classify_document(text_facture)
        for dt in DocumentType:
            if dt != DocumentType.INCONNU:
                assert dt.value in r.scores
