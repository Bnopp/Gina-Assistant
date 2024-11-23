import os
import json
import logging
from dotenv import load_dotenv
from gina.version import __version__

logger = logging.getLogger(__name__)

load_dotenv()


class Config:
    _config = None  # Cache for the loaded config file

    @classmethod
    def _load_config_file(cls, path: str = "config/config.json") -> dict:
        """Loads the configuration JSON file."""
        if cls._config is None:
            try:
                with open(path, "r") as file:
                    cls._config = json.load(file)
            except FileNotFoundError:
                logger.error(f"Configuration file '{path}' not found.")
                raise
            except json.JSONDecodeError:
                logger.error(f"Configuration file '{path}' contains invalid JSON.")
                raise
        return cls._config

    @classmethod
    def get_env_variable(cls, var_name: str) -> str:
        """Fetches an environment variable."""
        value = os.getenv(var_name)
        if not value:
            logger.error(f"Environment variable '{var_name}' is not set.")
            raise ValueError(f"Environment variable '{var_name}' is not set.")
        return value

    @classmethod
    def get_config_value(cls, key: str, default=None):
        """Fetches a value from the config file, with an optional default."""
        config = cls._load_config_file()
        return config.get(key, default)

    @classmethod
    def get_version(cls) -> str:
        """Returns the current version of the app."""
        return __version__
