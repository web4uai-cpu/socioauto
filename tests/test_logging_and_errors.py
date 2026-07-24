import json
import logging

import pytest

from src.logging_config import JsonFormatter, get_logger
from src.security.crypto import CryptoError, decrypt, encrypt


def test_get_logger_emits_valid_json(capsys):
    logger = get_logger("test.jsonlogger")
    logger.info("hello world", extra={"campaign_id": "abc123"})
    captured = capsys.readouterr()
    line = captured.out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["message"] == "hello world"
    assert payload["campaign_id"] == "abc123"
    assert payload["level"] == "INFO"


def test_json_formatter_includes_exception_info():
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=True,
        )
        import sys
        record.exc_info = sys.exc_info()
        formatted = formatter.format(record)
    payload = json.loads(formatted)
    assert "exception" in payload
    assert "boom" in payload["exception"]


def test_decrypt_invalid_ciphertext_raises_crypto_error():
    with pytest.raises(CryptoError):
        decrypt("not-valid-base64-ciphertext!!")


def test_decrypt_tampered_ciphertext_raises_crypto_error():
    ciphertext = encrypt("a-real-secret")
    tampered = ciphertext[:-4] + "abcd"
    with pytest.raises(CryptoError):
        decrypt(tampered)
