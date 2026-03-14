"""OpenAI environment helper.

Provides a small utility to load OPENAI_API_KEY from the environment or a local .env file
(if python-dotenv is installed). This centralizes key access and gives a clear error message
if the key is missing.

Do NOT add real API keys to the repository. Use environment variables or a local `.env` file.
"""

import os
from typing import Optional


def get_openai_api_key(required: bool = True) -> Optional[str]:
    """Return the OPENAI_API_KEY from environment or a local .env file.

    If python-dotenv is installed it will attempt to load variables from a `.env` file.

    Args:
        required: If True (default) raise RuntimeError when the key is missing. If False,
                  return None when the key is absent.

    Returns:
        The API key string or None.
    """
    # Try to load .env automatically if python-dotenv is available.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # dotenv is optional; ignore if not installed.
        pass

    key = os.getenv("OPENAI_API_KEY")

    if required and not key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Set it in your environment or in a local .env file (do not commit it). See README.md for details."
        )

    return key

