import logging

import pytest


def test_migrations_preserve_application_loggers(
    database_url: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.ml_client.base import logger as parser_logger
    from app.ml_client.safe import logger as safe_logger

    assert database_url.startswith("postgresql+psycopg://")
    assert parser_logger.disabled is False
    assert safe_logger.disabled is False
    with caplog.at_level(logging.WARNING):
        parser_logger.warning("ML logging survives database migrations")
    assert "ML logging survives database migrations" in caplog.text
