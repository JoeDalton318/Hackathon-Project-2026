import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.anomaly_model import DocumentAnomalyModel
from app.insee_client import InseeClient
from app.models import BatchInput, ValidationResult
from app.validation_engine import AnomalyEngine
from app.prepare_ml_data import generate_training_data, train_model

FIXTURES_DIR = Path("tests/fixtures")
ARTIFACTS_DIR = Path("artifacts")
MODEL_PATH = ARTIFACTS_DIR / "anomaly_model.joblib"


class UnavailableInseeClient(InseeClient):
    def get_establishment(self, siret: str):
        return {
            "found": False,
            "status": "error",
            "payload": {"error": "Simulated API outage"},
        }


def ensure_ml_model(model_path: Path) -> None:
    if model_path.exists():
        return

    print(f"[ML] Modèle absent : génération automatique dans {model_path}")
    generate_training_data()
    train_model()
    print("[ML] Modèle entraîné avec succès.")


def load_batch(filename: str) -> BatchInput:
    with open(FIXTURES_DIR / filename, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return BatchInput(**payload)


def load_ml_model() -> Optional[DocumentAnomalyModel]:
    if MODEL_PATH.exists():
        return DocumentAnomalyModel.load(str(MODEL_PATH))
    return None


def save_result(result: ValidationResult) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ARTIFACTS_DIR / f"{result.batch_id}_validation_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2, ensure_ascii=False))
    print(f"Saved result to: {output_path}")


def run_scenario(filename: str, use_unavailable_api: bool = False, disable_ml: bool = False) -> None:
    batch = load_batch(filename)

    if disable_ml:
        anomaly_model = None
    else:
        ensure_ml_model(MODEL_PATH)
        anomaly_model = load_ml_model()

    insee_client = (
        UnavailableInseeClient(enabled=True, fallback_to_mock=False)
        if use_unavailable_api
        else InseeClient(enabled=True, fallback_to_mock=True)
    )

    engine = AnomalyEngine(
        insee_client=insee_client,
        anomaly_model=anomaly_model,
        reference_date=datetime(2026, 3, 17, 12, 0, 0),
        engine_version="1.2.0",
    )

    result = engine.run(batch)

    print(f"\n===== RESULT FOR: {filename} =====\n")
    print(result.model_dump_json(indent=2, ensure_ascii=False))
    save_result(result)


if __name__ == "__main__":
    run_scenario("invalid_batch.json")
    run_scenario("valid_batch.json")
    run_scenario("api_unavailable_batch.json", use_unavailable_api=True)