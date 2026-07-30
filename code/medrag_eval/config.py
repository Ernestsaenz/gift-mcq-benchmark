from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_DB_PATH = "./runs/medrag_eval.sqlite"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    gift_api: str | None = field(default=None, repr=False)
    gift_email: str | None = field(default=None, repr=False)
    gift_password: str | None = field(default=None, repr=False)
    openrouter_api_key: str | None = field(default=None, repr=False)
    db_path: str = DEFAULT_DB_PATH

    @classmethod
    def from_env(cls, *, load_dotenv_file: bool = True) -> "Settings":
        if load_dotenv_file:
            _load_dotenv()
        return cls(
            gift_api=os.getenv("GIFT_API") or None,
            gift_email=os.getenv("GIFT_EMAIL") or None,
            gift_password=os.getenv("GIFT_PASSWORD") or None,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
            db_path=os.getenv("MEDRAG_EVAL_DB", DEFAULT_DB_PATH),
        )

    def as_redacted_dict(self) -> dict[str, str | None]:
        return {
            "gift_api": "[REDACTED]" if self.gift_api else None,
            "gift_email": "[REDACTED_EMAIL]" if self.gift_email else None,
            "gift_password": "[REDACTED]" if self.gift_password else None,
            "openrouter_api_key": "[REDACTED]" if self.openrouter_api_key else None,
            "db_path": str(self.db_path),
        }
