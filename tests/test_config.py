from pathlib import Path

import yaml

from notes_gen.config import Config, load_config, merge_cli_overrides, provider_of


def test_config_defaults():
    cfg = Config()
    assert cfg.output_dir == Path.home() / "notes"
    assert cfg.model == "anthropic/claude-sonnet-4-6"
    assert cfg.mermaid is True
    assert cfg.max_concurrent == 5
    assert cfg.web_max_pages == 50
    assert cfg.web_max_depth == 3
    assert cfg.api_keys == {}
    assert cfg.max_retries == 5
    assert cfg.retry_base_delay == 60.0
    assert cfg.verbose is False


def test_load_config_missing_file(tmp_path):
    missing = tmp_path / "nonexistent.yaml"
    cfg = load_config(missing)
    assert isinstance(cfg, Config)
    assert cfg.model == "anthropic/claude-sonnet-4-6"


def test_load_config_partial_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"model": "openai/gpt-4o", "web_max_pages": 10}))
    cfg = load_config(config_file)
    assert cfg.model == "openai/gpt-4o"
    assert cfg.web_max_pages == 10
    assert cfg.mermaid is True


def test_load_config_full_yaml(tmp_path):
    config_file = tmp_path / "config.yaml"
    data = {
        "output_dir": str(tmp_path / "out"),
        "model": "openai/gpt-4o",
        "mermaid": False,
        "max_concurrent": 3,
        "web_max_pages": 20,
        "web_max_depth": 2,
    }
    config_file.write_text(yaml.dump(data))
    cfg = load_config(config_file)
    assert cfg.output_dir == tmp_path / "out"
    assert cfg.model == "openai/gpt-4o"
    assert cfg.mermaid is False
    assert cfg.max_concurrent == 3


def test_load_config_api_keys(tmp_path):
    config_file = tmp_path / "config.yaml"
    data = {
        "model": "groq/llama-3.3-70b-versatile",
        "api_keys": {
            "groq": ["gsk_key1", "gsk_key2"],
            "openai": ["sk-key1"],
        },
    }
    config_file.write_text(yaml.dump(data))
    cfg = load_config(config_file)
    assert cfg.api_keys["groq"] == ["gsk_key1", "gsk_key2"]
    assert cfg.api_keys["openai"] == ["sk-key1"]


def test_load_config_api_keys_empty_list(tmp_path):
    config_file = tmp_path / "config.yaml"
    data = {"api_keys": {"anthropic": []}}
    config_file.write_text(yaml.dump(data))
    cfg = load_config(config_file)
    assert cfg.api_keys.get("anthropic") == []


def test_pick_api_key_returns_key_for_provider(tmp_path):
    cfg = Config(
        model="groq/llama-3.3-70b-versatile",
        api_keys={"groq": ["gsk_key1", "gsk_key2"]},
    )
    key = cfg.pick_api_key()
    assert key in ("gsk_key1", "gsk_key2")


def test_pick_api_key_returns_none_when_no_keys():
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={})
    assert cfg.pick_api_key() is None


def test_pick_api_key_returns_none_wrong_provider():
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={"openai": ["sk-key"]})
    assert cfg.pick_api_key() is None


def test_pick_api_key_rotates_randomly():
    cfg = Config(
        model="anthropic/claude-sonnet-4-6",
        api_keys={"anthropic": ["key-a", "key-b", "key-c"]},
    )
    results = {cfg.pick_api_key() for _ in range(50)}
    assert len(results) > 1  # rotation produces different keys


def test_merge_cli_overrides_none_values():
    cfg = Config()
    result = merge_cli_overrides(cfg, output_dir=None, model=None, mermaid=True)
    assert result.model == cfg.model
    assert result.mermaid is True


def test_merge_cli_overrides_with_values(tmp_path):
    cfg = Config()
    result = merge_cli_overrides(cfg, output_dir=tmp_path, model="openai/gpt-4o", mermaid=False)
    assert result.output_dir == tmp_path
    assert result.model == "openai/gpt-4o"
    assert result.mermaid is False


def test_merge_cli_preserves_api_keys():
    cfg = Config(api_keys={"groq": ["gsk_key"]})
    result = merge_cli_overrides(cfg, model="openai/gpt-4o")
    assert result.api_keys == {"groq": ["gsk_key"]}


def test_merge_cli_does_not_mutate_original():
    cfg = Config()
    original_model = cfg.model
    merge_cli_overrides(cfg, model="openai/gpt-4o")
    assert cfg.model == original_model


def test_load_config_retry_settings(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"max_retries": 3, "retry_base_delay": 30.0}))
    cfg = load_config(config_file)
    assert cfg.max_retries == 3
    assert cfg.retry_base_delay == 30.0


def test_load_config_tilde_expansion(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"output_dir": "~/notes"}))
    cfg = load_config(config_file)
    assert "~" not in str(cfg.output_dir)
    assert cfg.output_dir == Path.home() / "notes"


def test_pick_api_key_env_var_fallback(monkeypatch):
    monkeypatch.setenv("NOTEGEN_GROQ_KEY", "env-key-123")
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={})
    assert cfg.pick_api_key() == "env-key-123"


def test_pick_api_key_config_takes_priority_over_env(monkeypatch):
    monkeypatch.setenv("NOTEGEN_GROQ_KEY", "env-key")
    cfg = Config(model="groq/llama-3.3-70b-versatile", api_keys={"groq": ["config-key"]})
    assert cfg.pick_api_key() == "config-key"


def test_merge_cli_overrides_verbose():
    cfg = Config()
    result = merge_cli_overrides(cfg, verbose=True)
    assert result.verbose is True


def test_provider_of_with_slash():
    assert provider_of("anthropic/claude-sonnet-4-6") == "anthropic"
    assert provider_of("groq/llama-3.3-70b-versatile") == "groq"
    assert provider_of("nvidia_nim/meta/llama-3.3-70b-instruct") == "nvidia_nim"


def test_provider_of_without_slash():
    assert provider_of("ollama") == "ollama"


def test_merge_cli_overrides_template_applies_prompt():
    cfg = Config(prompt_templates={"code": "Focus on code."})
    result = merge_cli_overrides(cfg, template="code")
    assert "Focus on code." in result.extra_prompt


def test_merge_cli_overrides_template_appends_to_existing_prompt():
    cfg = Config(prompt_templates={"code": "Focus on code."}, extra_prompt="Be concise.")
    result = merge_cli_overrides(cfg, template="code")
    assert "Be concise." in result.extra_prompt
    assert "Focus on code." in result.extra_prompt


def test_merge_cli_overrides_unknown_template_ignored():
    cfg = Config(prompt_templates={"code": "Focus on code."})
    result = merge_cli_overrides(cfg, template="nonexistent")
    assert result.extra_prompt == ""


def test_merge_cli_overrides_toc_flag():
    cfg = Config()
    assert cfg.toc is False
    result = merge_cli_overrides(cfg, toc=True)
    assert result.toc is True
