from pathlib import Path

import yaml

from notes_gen.config import Config, load_config, merge_cli_overrides


def test_config_defaults():
    cfg = Config()
    assert cfg.output_dir == Path.home() / "notes"
    assert cfg.model == "anthropic/claude-sonnet-4-6"
    assert cfg.mermaid is True
    assert cfg.max_concurrent == 5
    assert cfg.web_max_pages == 50
    assert cfg.web_max_depth == 3


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
    assert cfg.mermaid is True  # default preserved


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


def test_merge_cli_does_not_mutate_original():
    cfg = Config()
    original_model = cfg.model
    merge_cli_overrides(cfg, model="openai/gpt-4o")
    assert cfg.model == original_model
