import os
from typing import Any, Dict, Optional
from .settings import settings
import requests


class InseeClient:

    def __init__(
        self,
        enabled: bool = False,
        fallback_to_mock: bool = True,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.enabled = enabled
        self.fallback_to_mock = fallback_to_mock
        self.base_url = base_url or settings.insee_base_url
        self.api_key = api_key or settings.insee_api_key

    def get_establishment(self, siret: str) -> Dict[str, Any]:
        if not self.enabled or not self.api_key:
            return self._mock_response(siret)

        url = f"{self.base_url}/siret/{siret}"
        headers = {
            "Accept": "application/json",
            "X-INSEE-Api-Key-Integration": self.api_key,
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                return {
                    "found": True,
                    "status": "ok",
                    "payload": response.json(),
                }

            if response.status_code == 404:
                return {
                    "found": False,
                    "status": "not_found",
                    "payload": {},
                }

            if self.fallback_to_mock:
                mock_result = self._mock_response(siret)
                mock_result["status"] = "api_error_mock_fallback"
                return mock_result

            return {
                "found": False,
                "status": "error",
                "payload": {
                    "status_code": response.status_code,
                    "text": response.text,
                },
            }

        except Exception as exc:
            if self.fallback_to_mock:
                mock_result = self._mock_response(siret)
                mock_result["status"] = "api_exception_mock_fallback"
                mock_result["payload"] = {
                    **mock_result.get("payload", {}),
                    "api_error": str(exc),
                }
                return mock_result

            return {
                "found": False,
                "status": "error",
                "payload": {"error": str(exc)},
            }

    def _mock_response(self, siret: str) -> Dict[str, Any]:
        known_valid_sirets = {
            "42385519600014": {
                "denomination": "EPITECH ECOLE INFORMATIQUE NOUV TECHNOL",
                "etatAdministratifEtablissement": "A",
            },
            "55210055400013": {
                "denomination": "BETA CONSEIL",
                "etatAdministratifEtablissement": "A",
            },
            "73282932000074": {
                "denomination": "ACME SARL",
                "etatAdministratifEtablissement": "A",
            },
        }

        if siret in known_valid_sirets:
            return {
                "found": True,
                "status": "mock",
                "payload": known_valid_sirets[siret],
            }

        return {
            "found": False,
            "status": "mock",
            "payload": {},
        }