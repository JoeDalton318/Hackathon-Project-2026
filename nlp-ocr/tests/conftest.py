"""tests/conftest.py — Fixtures partagées."""
import sys
from pathlib import Path
import pytest

# Le répertoire racine du projet est le parent de tests/
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def text_facture():
    return """
FACTURE

Numéro de facture : FAC-2024-0042
Date d'émission : 15/03/2024
Date d'échéance : 14/04/2024

DUPONT SERVICES SARL
12 rue de la Paix
75001 Paris
SIRET : 83245678901230
TVA : FR12832456789
Tél : 01 23 45 67 89
Email : contact@dupont-services.fr
IBAN : FR76 3000 6000 0112 3456 7890 189
BIC : BNPAFRPP

Destinataire :
CLIENT CONSULTING SAS
5 avenue Victor Hugo
69001 Lyon

Montant HT : 7 000,00 €
TVA (20%) : 1 400,00 €
Total TTC : 8 400,00 €
"""

@pytest.fixture(scope="session")
def text_urssaf_valid():
    return """
ATTESTATION DE VIGILANCE
URSSAF Île-de-France
N° d'attestation : ATT987654
DUPONT SERVICES SARL
SIRET : 83245678901230
Date d'émission   : 01/01/2024
Date d'expiration : 30/06/2099
Document valide du 01/01/2024 au 30/06/2099
Vérifiable sur net-entreprises.fr
"""

@pytest.fixture(scope="session")
def text_urssaf_expired():
    return """
ATTESTATION DE VIGILANCE
URSSAF Île-de-France
N° d'attestation : ATT112233
LEROY CONSEIL SAS
SIRET : 41234567890120
Date d'émission   : 01/01/2022
Date d'expiration : 30/06/2022
Document valide du 01/01/2022 au 30/06/2022
"""

@pytest.fixture(scope="session")
def text_rib():
    return """
RELEVÉ D'IDENTITÉ BANCAIRE (RIB)
Titulaire : DUPONT SERVICES SARL
SIRET : 83245678901230
Domiciliation : BNP Paribas
IBAN : FR76 3000 6000 0112 3456 7890 189
BIC  : BNPAFRPP
"""

@pytest.fixture(scope="session")
def text_kbis():
    return """
EXTRAIT KBIS
Registre du Commerce et des Sociétés
Greffe du Tribunal de Commerce de Paris
SIREN : 832456789
Forme juridique : SARL
Capital social : 10 000 €
Date d'immatriculation : 15/03/2018
Dirigeant : Jean Dupont
RCS Paris
"""

@pytest.fixture(scope="session")
def valid_siret():
    sys.path.insert(0, str(ROOT))
    from scripts.generate_dataset import gen_siret
    return gen_siret()

@pytest.fixture(scope="session")
def valid_company():
    from scripts.generate_dataset import gen_company
    return gen_company()
