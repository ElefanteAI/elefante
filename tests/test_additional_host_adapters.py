"""Isolated lifecycle contracts for Zed and Continue adapters."""

import json

from scripts.setup import configure_additional_hosts as module
from scripts.setup.install_manifest import configured_surfaces, remove_unchanged_files


def test_detection_is_read_only_and_host_specific(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    before = sorted(path.relative_to(home) for path in home.rglob("*"))
    assert module.detect_additional_hosts(
        home=home, which=lambda _name: None
    ) == set()
    assert sorted(path.relative_to(home) for path in home.rglob("*")) == before

    (home / ".config" / "zed").mkdir(parents=True)
    (home / ".continue").mkdir()
    assert module.detect_additional_hosts(
        home=home, which=lambda _name: None
    ) == {"zed", "continue"}


def test_zed_adapter_preserves_unrelated_settings_and_owns_exact_entry(tmp_path):
    home = tmp_path / "home"
    path = home / ".config" / "zed" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"theme": "One Dark", "context_servers": {"other": {"command": "other"}}}),
        encoding="utf-8",
    )

    assert module.configure_zed(
        path, tmp_path / "runtime", "/python", manifest_home=home
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["theme"] == "One Dark"
    assert payload["context_servers"]["other"] == {"command": "other"}
    entry = payload["context_servers"]["elefante"]
    assert entry["args"] == ["-m", "src.mcp.stdio_bridge"]
    assert entry["env"]["ELEFANTE_CLIENT_TOOL"] == "zed"
    assert configured_surfaces(home) == {"zed"}

    removed, preserved = remove_unchanged_files(home, apply=True)
    assert removed == [path]
    assert preserved == []
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {"theme": "One Dark", "context_servers": {"other": {"command": "other"}}}


def test_zed_preserves_user_owned_or_invalid_configuration(tmp_path):
    home = tmp_path / "home"
    path = home / ".config" / "zed" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"context_servers": {"elefante": {"command": "mine"}}}),
        encoding="utf-8",
    )
    assert not module.configure_zed(
        path, tmp_path / "runtime", "/python", manifest_home=home
    )
    assert json.loads(path.read_text())["context_servers"]["elefante"] == {
        "command": "mine"
    }
    path.write_text("// jsonc user settings", encoding="utf-8")
    assert not module.configure_zed(
        path, tmp_path / "runtime", "/python", manifest_home=home
    )
    assert path.read_text(encoding="utf-8") == "// jsonc user settings"


def test_continue_adapter_uses_dedicated_owned_block_and_safe_uninstall(tmp_path):
    home = tmp_path / "home"
    path = home / ".continue" / "mcpServers" / "elefante.yaml"
    assert module.configure_continue(
        path, tmp_path / "runtime", "/python", manifest_home=home
    )
    content = path.read_text(encoding="utf-8")
    assert "schema: v1" in content
    assert "type: stdio" in content
    assert "src.mcp.stdio_bridge" in content
    assert "ELEFANTE_CLIENT_TOOL: \"continue\"" in content
    assert configured_surfaces(home) == {"continue"}

    removed, preserved = remove_unchanged_files(home, apply=True)
    assert removed == [path]
    assert preserved == []
    assert not path.exists()


def test_continue_preserves_user_owned_or_modified_block(tmp_path):
    home = tmp_path / "home"
    path = home / ".continue" / "mcpServers" / "elefante.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("name: User Elefante\n", encoding="utf-8")
    assert not module.configure_continue(
        path, tmp_path / "runtime", "/python", manifest_home=home
    )
    assert path.read_text(encoding="utf-8") == "name: User Elefante\n"


def test_detected_adapter_selection_does_not_touch_unselected_host(tmp_path):
    home = tmp_path / "home"
    (home / ".config" / "zed").mkdir(parents=True)
    (home / ".continue").mkdir(parents=True)
    results = module.configure_detected_additional_hosts(
        tmp_path / "runtime",
        "/python",
        home=home,
        selected={"zed"},
        which=lambda _name: None,
    )
    assert results == {"zed": True}
    assert not (home / ".continue" / "mcpServers" / "elefante.yaml").exists()
