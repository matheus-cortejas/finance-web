# config_loader.py
import os
import re
import yaml
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

def _substituir_env(obj):
    """Substitui recursivamente placeholders ${VAR} pelos valores de ambiente."""
    if isinstance(obj, dict):
        return {k: _substituir_env(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substituir_env(item) for item in obj]
    elif isinstance(obj, str):
        padrao = re.compile(r'\$\{([^}]+)\}')
        def repl(match):
            var = match.group(1)
            return os.getenv(var, match.group(0))  # mantém se não existir
        return padrao.sub(repl, obj)
    else:
        return obj

@lru_cache(maxsize=1)
def load_global_config():
    cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    return _substituir_env(config)