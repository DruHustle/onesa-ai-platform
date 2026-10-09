"""Generate local secrets once, without overwriting or printing them."""

import os
import secrets
from pathlib import Path

path = Path(__file__).resolve().parents[1] / ".env"
content = (
    "ONESA_DB_PASSWORD=" + secrets.token_urlsafe(32) + "\n"
    "ONESA_METRICS_TOKEN=" + secrets.token_urlsafe(32) + "\n"
    "ONESA_MODEL_API_KEY=" + secrets.token_urlsafe(32) + "\n"
    "ONESA_PUBLIC_ORIGIN=http://localhost:3100\n"
    "ONESA_CHAT_PORT=3100\nONESA_MODEL_BACKEND=mock\n"
)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as file:
    file.write(content)
print(
    "Created .env with private local secrets. Adjust the port/origin before starting if needed."
)
