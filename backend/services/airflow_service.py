import httpx

from app.config import settings


async def trigger_pipeline(document_id: str) -> bool:
    url = f"{settings.AIRFLOW_URL}/api/v1/dags/{settings.AIRFLOW_DAG_ID}/dagRuns"
    payload = {"conf": {"document_id": document_id}}
    auth = (settings.AIRFLOW_USERNAME, settings.AIRFLOW_PASSWORD)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload, auth=auth)
            response.raise_for_status()
            return True
    except httpx.HTTPError:
        return False