import pytest

from app.config import Settings

pytestmark = pytest.mark.unit


def test_database_url_is_built_from_components():
    settings = Settings(
        postgres_host="db-host",
        postgres_port=5433,
        postgres_user="alice",
        postgres_password="secret",
        postgres_db="shipyard_test",
        _env_file=None,
    )

    assert settings.database_url == "postgresql+asyncpg://alice:secret@db-host:5433/shipyard_test"


def test_database_url_override_takes_precedence():
    settings = Settings(
        postgres_host="db-host",
        database_url_override="postgresql+asyncpg://override/db",
        _env_file=None,
    )

    assert settings.database_url == "postgresql+asyncpg://override/db"


def test_defaults_are_sane_for_local_development():
    settings = Settings(_env_file=None)

    assert settings.app_env == "development"
    assert settings.app_name == "shipyard"
    assert settings.db_pool_size > 0


@pytest.mark.parametrize("value", ["development", "test", "production"])
def test_app_env_accepts_known_literals(value):
    settings = Settings(app_env=value, _env_file=None)
    assert settings.app_env == value


def test_app_env_rejects_unknown_value():
    with pytest.raises(ValueError):
        Settings(app_env="staging", _env_file=None)
