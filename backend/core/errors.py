import subprocess

import requests

from backend.core.config import redact


class ControlError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        self.status, self.code, self.message, self.details = status, code, message, details
        super().__init__(message)


def translate(exc: Exception) -> ControlError:
    if isinstance(exc, ControlError):
        return exc
    text = redact(str(exc))
    if type(exc).__module__.startswith("openai"):
        return ControlError(
            502,
            "LLM_ERROR",
            "Generovanie modelom zlyhalo. Skontrolujte OpenAI pripojenie, kľúč a dostupnosť modelu.",
            text,
        )
    if isinstance(exc, requests.HTTPError):
        status = exc.response.status_code if exc.response is not None else 502
        if status in (401, 403):
            return ControlError(
                502, "AZURE_ACCESS", "Azure odmietlo prístup. Skontrolujte PAT a oprávnenia."
            )
        if status == 404:
            return ControlError(404, "NOT_FOUND", "User Story alebo projekt sa nenašiel.")
    if "401" in text or "403" in text or "authorization failed" in text:
        return ControlError(
            502,
            "AZURE_ACCESS",
            "Prístup k externej službe bol odmietnutý. Skontrolujte konfiguráciu.",
        )
    if "404" in text or isinstance(exc, FileNotFoundError):
        return ControlError(404, "NOT_FOUND", "Požadované údaje sa nenašli.", text)
    if "Draft changed" in text or "Draft changed since" in text or "revision mismatch" in text:
        return ControlError(
            409,
            "STALE_REVIEW",
            "Koncept sa zmenil. Načítajte aktuálnu verziu; vaše úpravy zostali na obrazovke.",
        )
    if "Another workflow" in text:
        return ControlError(
            409, "BUSY", "Generátor práve pracuje. Počkajte na dokončenie operácie."
        )
    if isinstance(exc, ValueError):
        return ControlError(
            422, "VALIDATION", "Údaje neprešli kontrolou. Skontrolujte uvedené podrobnosti.", text
        )
    if isinstance(exc, subprocess.CalledProcessError):
        return ControlError(
            500,
            "WORKFLOW_FAILED",
            "Generovanie, spustenie alebo publikovanie zlyhalo. Pozrite si denník operácie.",
        )
    return ControlError(
        502,
        "SERVICE_ERROR",
        "Operáciu sa nepodarilo dokončiť. Skontrolujte pripojenie a denník.",
        text,
    )
