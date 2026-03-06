"""Configuration loading — INI file + environment variable overlay."""

import configparser
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    """Application configuration with defaults matching config.example.ini."""

    dsn: str = ""
    connection_string: str = ""
    username: str = ""
    password: str = ""
    database: str = ""
    query_timeout: int = 30
    preview_rows: int = 20
    log_file: str = "estship_upload.log"
    log_level: str = "INFO"
    config_path: str = ""

    def build_connection_string(self) -> str:
        """Assemble a pyodbc connection string from config fields."""
        if self.connection_string:
            cs = self.connection_string
        else:
            cs = f"DSN={self.dsn}"

        if self.username and "UID=" not in cs.upper():
            cs += f";UID={self.username}"
        if self.password and "PWD=" not in cs.upper():
            cs += f";PWD={self.password}"

        return cs


def load_config(config_path: str | None = None) -> AppConfig:
    """Load config from INI file with environment variable overlay.

    Precedence (highest first):
    1. Environment variables (ESTSHIP_DB_*)
    2. INI file
    3. Dataclass defaults
    """
    config = AppConfig()

    # Find and parse INI file
    ini = configparser.ConfigParser()
    ini.optionxform = str  # preserve key casing

    resolved_path = ""
    if config_path and Path(config_path).exists():
        resolved_path = config_path
    elif Path("config/config.ini").exists():
        resolved_path = "config/config.ini"

    if resolved_path:
        ini.read(resolved_path)
        config.config_path = resolved_path

    # Apply INI values
    if ini.has_section("database"):
        db = dict(ini["database"])
        if "dsn" in db:
            config.dsn = db["dsn"]
        if "connection_string" in db:
            config.connection_string = db["connection_string"]
        if "username" in db:
            config.username = db["username"]
        if "password" in db:
            config.password = db["password"]

    if ini.has_section("settings"):
        settings = dict(ini["settings"])
        if "database" in settings:
            config.database = settings["database"]
        if "query_timeout" in settings:
            config.query_timeout = int(settings["query_timeout"])
        if "preview_rows" in settings:
            config.preview_rows = int(settings["preview_rows"])

    if ini.has_section("logging"):
        log = dict(ini["logging"])
        if "log_file" in log:
            config.log_file = log["log_file"]
        if "log_level" in log:
            config.log_level = log["log_level"]

    # Environment variable overlay (highest priority)
    env_dsn = os.environ.get("ESTSHIP_DB_DSN")
    if env_dsn:
        config.dsn = env_dsn

    env_user = os.environ.get("ESTSHIP_DB_USER")
    if env_user:
        config.username = env_user

    env_pwd = os.environ.get("ESTSHIP_DB_PASSWORD")
    if env_pwd:
        config.password = env_pwd

    env_cs = os.environ.get("ESTSHIP_DB_CONNECTION_STRING")
    if env_cs:
        config.connection_string = env_cs

    return config


def save_credentials(config: AppConfig) -> None:
    """Persist username and password to the INI file that was loaded."""
    path = config.config_path or "config/config.ini"
    ini = configparser.ConfigParser()
    ini.optionxform = str

    if Path(path).exists():
        ini.read(path)

    if not ini.has_section("database"):
        ini.add_section("database")

    ini.set("database", "dsn", config.dsn)
    ini.set("database", "username", config.username)
    ini.set("database", "password", config.password)

    if not ini.has_section("settings"):
        ini.add_section("settings")
    ini.set("settings", "database", config.database)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        ini.write(f)
