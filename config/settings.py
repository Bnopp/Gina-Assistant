import os
import json
import logging
from gina.version import __version__

logger = logging.getLogger(__name__)


class Config:
    def __init__(self, config_file="config/config.json"):
        self.config = self._load_config_file(config_file)

    def _load_config_file(self, path: str) -> dict:
        """Loads the configuration JSON file."""
        try:
            with open(path, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            logger.error(f"Configuration file '{path}' not found.")
            raise
        except json.JSONDecodeError:
            logger.error(f"Configuration file '{path}' contains invalid JSON.")
            raise

    def get_env_variable(self, var_name: str) -> str:
        """Fetches an environment variable."""
        value = os.getenv(var_name)
        if not value:
            logger.error(f"Environment variable '{var_name}' is not set.")
            raise ValueError(f"Environment variable '{var_name}' is not set.")
        return value

    def get_config_value(self, key: str, default=None):
        """Fetches a value from the config file, with an optional default."""
        return self.config.get(key, default)
    
    def get_version(self) -> str:
        """Returns the current version of the app."""
        return __version__
