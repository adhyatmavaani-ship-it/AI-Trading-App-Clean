from pathlib import Path

from scripts.advanced_trading_env import generate_secret, parse_env_file, render_env_block, validate_values, write_missing_values


def test_generated_secret_is_valid_for_api_key_encryption() -> None:
    values = {
        "USER_API_KEY_ENCRYPTION_SECRET": generate_secret(),
        "ML_SIGNAL_PIPELINE_ENABLED": "true",
        "ML_SIGNAL_PIPELINE_INTERVAL_SECONDS": "5.0",
        "CHART_EXECUTION_BRIDGE_ENABLED": "true",
        "CHART_EXECUTION_BRIDGE_INTERVAL_SECONDS": "1.0",
        "CHART_EXECUTION_BRIDGE_MODE": "mock",
    }

    assert validate_values(values) == []


def test_env_block_contains_staging_worker_settings() -> None:
    block = render_env_block("test-secret-value")

    assert "USER_API_KEY_ENCRYPTION_SECRET=test-secret-value" in block
    assert "ML_SIGNAL_PIPELINE_ENABLED=true" in block
    assert "CHART_EXECUTION_BRIDGE_ENABLED=true" in block
    assert "CHART_EXECUTION_BRIDGE_MODE=mock" in block


def test_write_missing_values_preserves_existing_env(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("EXISTING=value\nCHART_EXECUTION_BRIDGE_MODE=testnet\n", encoding="utf-8")

    write_missing_values(
        env_path,
        {
            "USER_API_KEY_ENCRYPTION_SECRET": generate_secret(),
            "CHART_EXECUTION_BRIDGE_MODE": "mock",
        },
    )
    values = parse_env_file(env_path)

    assert values["EXISTING"] == "value"
    assert values["CHART_EXECUTION_BRIDGE_MODE"] == "testnet"
    assert values["USER_API_KEY_ENCRYPTION_SECRET"]
