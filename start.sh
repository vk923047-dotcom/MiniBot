
#!/usr/bin/env bash
set -e

python - <<'PY'
import json
import os
from pathlib import Path

required = [
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "STREAMLIT_AUTH_COOKIE_SECRET",
]

missing = [name for name in required if not os.environ.get(name)]
if missing:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(missing)
    )

settings = {
    "redirect_uri": "https://minibot-cnqh.onrender.com/oauth2callback",
    "cookie_secret": os.environ["STREAMLIT_AUTH_COOKIE_SECRET"],
    "client_id": os.environ["GOOGLE_CLIENT_ID"],
    "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
    "server_metadata_url":
        "https://accounts.google.com/.well-known/openid-configuration",
}

folder = Path(".streamlit")
folder.mkdir(exist_ok=True)

content = "[auth]\n" + "".join(
    f"{key} = {json.dumps(value)}\n"
    for key, value in settings.items()
)

(folder / "secrets.toml").write_text(content, encoding="utf-8")
print("Streamlit authentication configuration created.")
PY

exec streamlit run app.py \
    --server.address 0.0.0.0 \
    --server.port "${PORT:-10000}"
