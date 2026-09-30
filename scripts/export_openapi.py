"""Export the exact FastAPI OpenAPI document to the repository root."""

import json
from pathlib import Path

from app.main import app


Path("openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
print("Wrote openapi.json")
