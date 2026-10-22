"""Optional Azure Translator REST API used ahead of best-effort public providers.

This avoids reliance on Google/MyMemory scraping from shared cloud-hosting IPs.
It is not an offline model; the user must explicitly configure a Translator key.
"""
from __future__ import annotations

import os
import requests

_TRANSLATOR_URL = 'https://api.cognitive.microsofttranslator.com/translate'


def azure_configured() -> bool:
    return bool(os.environ.get('TBA_AZURE_TRANSLATOR_KEY', '').strip())


class AzureTranslator:
    def __init__(self, target: str):
        if target not in {'hi', 'mr', 'bho', 'ml'}:
            raise ValueError('Unsupported Azure target language')
        self.target = target

    def translate(self, text: str) -> str:
        key = os.environ.get('TBA_AZURE_TRANSLATOR_KEY', '').strip()
        if not key:
            raise RuntimeError('Azure Translator is not configured')
        headers = {
            'Ocp-Apim-Subscription-Key': key,
            'Content-Type': 'application/json',
        }
        region = os.environ.get('TBA_AZURE_TRANSLATOR_REGION', '').strip()
        if region:
            headers['Ocp-Apim-Subscription-Region'] = region
        response = requests.post(
            _TRANSLATOR_URL,
            params={'api-version': '3.0', 'from': 'en', 'to': self.target},
            headers=headers,
            json=[{'Text': text}],
            timeout=(4, 16),
        )
        response.raise_for_status()
        data = response.json()
        translated = data[0]['translations'][0]['text']
        if not isinstance(translated, str) or not translated.strip():
            raise ValueError('Azure Translator returned empty text')
        return translated.strip()
