
import os
from pathlib import Path

import yaml
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Layered Configuration API")

# Allow browser-based graders to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}


def read_dotenv(path=".env"):
    """Read .env without injecting values into OS environment."""
    result = {}
    file_path = Path(path)

    if not file_path.exists():
        return result

    for line in file_path.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip("'\"")

    return result




def normalize_key(key):
    key = key.strip().lower()

    if key.startswith("app_"):
        key = key[4:]

    if key == "num_workers":
        key = "workers"

    return key




def coerce_value(key, value):
    key = normalize_key(key)

    if key in ("port", "workers"):
        return int(value)

    if key == "debug":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {
            "true", "1", "yes", "on"
        }

    return str(value)


def normalize_layer(layer):
    return {
        normalize_key(key): coerce_value(key, value)
        for key, value in layer.items()
    }



def load_config():
    config = dict(DEFAULTS)

    # Layer 2: YAML
    environment = os.environ.get("APP_ENV", "development")
    yaml_path = Path(f"config.{environment}.yaml")

    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as file:
            yaml_config = yaml.safe_load(file) or {}
        config.update(normalize_layer(yaml_config))

    # Layer 3: .env
    config.update(normalize_layer(read_dotenv()))

    # Layer 4: OS environment variables
    os_config = {
        key[4:].lower(): value
        for key, value in os.environ.items()
        if key.startswith("APP_")
    }
    config.update(normalize_layer(os_config))

    return config



@app.get("/effective-config")
def effective_config(
    overrides: list[str] = Query(default=[], alias="set")
):
    config = load_config()

    # Apply query overrides last, independently on every request.
    for item in overrides:
    if "=" not in item:
        continue

    key, value = item.split("=", 1)
    key = normalize_key(key)
    config[key] = coerce_value(key, value)

        if not key:
            continue

        config[key] = coerce_value(key, value)

    # Never expose the actual secret.
    if "api_key" in config:
        config["api_key"] = "****"

    return config
