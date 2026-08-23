"""Open-source local LLM adapter using Ollama's local HTTP API."""

import json
import os
from typing import Any, Dict, Optional

import requests


class OllamaClient:
    """Client for local models such as Mistral, Llama 3, or Gemma."""

    def __init__(self, model: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model or os.getenv("OLLAMA_MODEL", "mistral")
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    @property
    def enabled(self) -> bool:
        """Return whether Ollama is reachable."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=1)
            return response.ok
        except requests.RequestException:
            return False

    def generate(self, prompt: str, system: str = "") -> str:
        """Generate text from the configured local open-source model."""
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "system": system, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        return response.json().get("response", "")

    def generate_json(self, prompt: str, system: str = "") -> Dict[str, Any]:
        """Generate and parse a JSON response from the local model."""
        text = self.generate(prompt, system)
        return json.loads(text)
