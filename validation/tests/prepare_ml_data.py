import json
import random
from pathlib import Path

from app.anomaly_model import DocumentAnomalyModel
from app.models import BatchInput

TRAIN_DIR = Path("curated/ml_train_normal")
MODEL_PATH = "curated/anomaly_model.joblib"


def make_normal_sample(idx: int) -> dict:
    base_amount_ht = random.choice([150, 200, 350, 500, 750, 1000, 1200, 1500, 2000, 2500, 3000])
    base_tva = round(base_amount_ht * 0.20, 2)
    base_ttc = round(base_amount_ht + base_tva, 2)

    day = random.randint(1, 20)
    due_day = min(day + random.randint(10, 20), 28)

    return {
        "batch_id": f"batch_train_{idx:03d}",
        "documents": [
            {
                "document_id": f"doc_fact_{idx:03d}",
                "doc_type": "facture",
                "fields": {
                    "numero_facture": f"FAC-2026-{idx:03d}",
                    "date_facture": f"2026-03-{day:02d}",
                    "date_echeance": f"2026-04-{due_day:02d}",
                    "fournisseur": {
                        "raison_sociale": "EPITECH",
                        "siret": "42385519600014",
                        "tva_intracommunautaire": "FR69423855196"
                    },
                    "client": {
                        "raison_sociale": "CLIENT XYZ",
                        "siret": "42385519600014"
                    },
                    "amount_ht": base_amount_ht,
                    "amount_tva": base_tva,
                    "amount_ttc": base_ttc,
                    "confidence": round(random.uniform(0.85, 0.99), 3)
                },
                "metadata": {}
            },
            {
                "document_id": f"doc_att_{idx:03d}",
                "doc_type": "attestation_siret",
                "fields": {
                    "supplier_name": "EPITECH",
                    "siret": "42385519600014",
                    "date_emission": "2026-01-01",
                    "date_expiration": "2026-12-31"
                },
                "metadata": {}
            },
            {
                "document_id": f"doc_rib_{idx:03d}",
                "doc_type": "rib",
                "fields": {
                    "supplier_name": "EPITECH",
                    "iban": "FR7630006000001123456789018",
                    "bic": "AGRIFRPP",
                    "titulaire": "EPITECH"
                },
                "metadata": {}
            }
        ]
    }


def generate_training_data(n_samples: int = 40):
    TRAIN_DIR.mkdir(parents=True, exist_ok=True)

    for i in range(1, n_samples + 1):
        payload = make_normal_sample(i)
        output_path = TRAIN_DIR / f"normal_batch_{i:03d}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Generated training data in: {TRAIN_DIR.resolve()}")


def load_batches(train_dir: Path):
    batches = []
    for file_path in sorted(train_dir.glob("*.json")):
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        batches.append(BatchInput(**payload))
    return batches


def train_model():
    batches = load_batches(TRAIN_DIR)

    model = DocumentAnomalyModel(
        contamination=0.05,
        random_state=42,
        enabled=True,
    )
    model.fit(batches)
    model.save(MODEL_PATH)

    print(f"Model trained on {len(batches)} batches and saved to: {MODEL_PATH}")


if __name__ == "__main__":
    generate_training_data()
    train_model()