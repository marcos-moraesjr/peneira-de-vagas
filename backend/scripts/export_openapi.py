"""Grava o OpenAPI da API em frontend/src/api/openapi.json (base dos tipos do front).

Uso, a partir da raiz: python -m backend.scripts.export_openapi
"""
import json
from pathlib import Path

from backend.app.config import load_settings
from backend.app.main import DEFAULT_CONFIG, create_app

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "api" / "openapi.json"


def main() -> None:
    app = create_app(load_settings(DEFAULT_CONFIG), sources_factory=list)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OpenAPI gravado em {OUTPUT}")


if __name__ == "__main__":
    main()
