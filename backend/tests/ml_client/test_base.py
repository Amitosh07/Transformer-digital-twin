import pytest

from app.ml_client.base import (
    MLClientError,
    MLTimeoutError,
    MLTwinClient,
    parse_ml_result,
    validate_history,
    validate_result_identity,
)
from app.ml_client.stub_client import StubMLTwinClient
from app.schemas.analytics import MLResultIn
from app.schemas.telemetry import TelemetryIn
from app.schemas.transformer import TransformerOut


def test_protocol_and_error_hierarchy() -> None:
    assert isinstance(StubMLTwinClient(), MLTwinClient)
    assert issubclass(MLTimeoutError, MLClientError)


def test_parser_drops_unknown_keys_and_rejects_missing_fields(
    valid_result: MLResultIn,
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = valid_result.model_dump()
    payload["extra_prediction_metadata"] = "private value"
    assert parse_ml_result(payload) == valid_result
    assert "extra_prediction_metadata" in caplog.text
    assert "private value" not in caplog.text
    del payload["model_version"]
    with pytest.raises(MLClientError, match="required fields"):
        parse_ml_result(payload)


@pytest.mark.parametrize("value", [None, [], "not an object", 0])
def test_parser_requires_object(value: object) -> None:
    with pytest.raises(MLClientError, match="object"):
        parse_ml_result(value)


def test_parser_revalidates_mutated_models(valid_result: MLResultIn) -> None:
    valid_result.health_index = 120
    with pytest.raises(MLClientError):
        parse_ml_result(valid_result)


def test_valid_history_is_unchanged(
    transformer: TransformerOut,
    record: TelemetryIn,
    history: list[TelemetryIn],
) -> None:
    before = [row.model_dump() for row in history]
    validate_history(transformer, record, history, 60)
    assert before == [row.model_dump() for row in history]


@pytest.mark.parametrize(
    "case",
    ["current", "future", "wrong_asset", "reversed", "duplicate", "too_long", "wrong_transformer"],
)
def test_invalid_history_contract(
    case: str,
    transformer: TransformerOut,
    record: TelemetryIn,
    history: list[TelemetryIn],
) -> None:
    from datetime import timedelta

    window = 60
    if case == "current":
        history.append(record)
    elif case == "future":
        history.append(
            record.model_copy(update={"timestamp": record.timestamp + timedelta(seconds=1)})
        )
    elif case == "wrong_asset":
        history[0] = history[0].model_copy(update={"transformer_id": "TX-OTHER"})
    elif case == "reversed":
        history.reverse()
    elif case == "duplicate":
        history[1] = history[0]
    elif case == "too_long":
        window = 1
    else:
        transformer = transformer.model_copy(update={"id": "TX-OTHER"})
    with pytest.raises(MLClientError):
        validate_history(transformer, record, history, window)


def test_result_identity_matches_current_record(
    valid_result: MLResultIn, record: TelemetryIn
) -> None:
    assert validate_result_identity(valid_result, record) is valid_result
    with pytest.raises(MLClientError):
        validate_result_identity(
            valid_result.model_copy(update={"transformer_id": "TX-OTHER"}), record
        )


def test_documented_json_examples_match_adapter() -> None:
    import json
    import re
    from pathlib import Path

    notes = (Path(__file__).resolve().parents[2] / "docs/ml-integration-notes.md").read_text()
    blocks = re.findall(r"```json\n(.*?)\n```", notes, re.DOTALL)
    assert len(blocks) == 2
    request, response = [json.loads(block) for block in blocks]
    transformer = TransformerOut.model_validate(request["transformer"])
    record = TelemetryIn.model_validate(request["record"])
    history = [TelemetryIn.model_validate(row) for row in request["history"]]
    assert MLResultIn.model_validate(response) == StubMLTwinClient().analyze(
        transformer,
        record,
        history,
    )
