#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# ================================================== #

import json
import zipfile
from types import SimpleNamespace

from pygpt_net.core.profile_exporter import ProfileExporter

CONFIG = {
    "api_key": "sk-top",
    "azure_api_key": "az",
    "max_tokens": 4096,
    "max_output_tokens": "2048",
    "providers": {
        "openai": {"api_key": "sk-openai", "api_base": "https://api.openai.com/v1"},
        "anthropic": {"api_key": "", "extra": {"client_secret": "cs"}},
    },
    "api_custom_providers": [{"name": "x", "api_key": "custom", "api_endpoint": "https://x"}],
    "plugins": {
        "slack": {"bot_token": "xoxb", "enabled": True},
        "server": {"smtp_password": "pw", "telnet_password_prompt": "Password:"},
        "mcp": {"servers": [{"authorization": "Bearer abc", "env": "KEY=1", "headers": "X: y",
                             "bearer_token_env_var": "MY_VAR", "tool_timeout_sec": "5"}]},
        "tuya": {"tuya_access_token": "t", "tuya_token_expire_at": "123", "tuya_token_get": True},
    },
    "app.env": {"OPENAI_API_KEY": "sk-env", "HOME_DIR": "/home"},
    "security.prompt_injection.prompt": "token of trust",
}


def test_is_secret_key_classification():
    yes = ["api_key", "API_KEY", "custom_api_key", "apikey", "bot_token", "token", "oauth_token",
           "tuya_access_token", "client_secret", "smtp_password", "passwd", "authorization",
           "bearer_token", "env", "headers", "env_http_headers", "google_maps_api_key", "credentials"]
    no = ["max_tokens", "summary_max_tokens", "telnet_password_prompt", "bearer_token_env_var",
          "tuya_token_expire_at", "tuya_token_expires_in", "tuya_token_get", "fb_token_extend",
          "bb_set_app_password", "api_base", "model", "", None, "tokens"]
    for key in yes:
        assert ProfileExporter.is_secret_key(key) is True, key
    for key in no:
        assert ProfileExporter.is_secret_key(key) is False, key


def test_redact_secrets_blanks_only_string_credentials():
    redacted, count = ProfileExporter.redact_secrets(CONFIG)

    assert redacted["api_key"] == "" and redacted["azure_api_key"] == ""
    assert redacted["providers"]["openai"]["api_key"] == ""
    assert redacted["providers"]["openai"]["api_base"] == "https://api.openai.com/v1"
    assert redacted["providers"]["anthropic"]["extra"]["client_secret"] == ""
    assert redacted["api_custom_providers"][0]["api_key"] == ""
    assert redacted["api_custom_providers"][0]["api_endpoint"] == "https://x"
    assert redacted["plugins"]["slack"] == {"bot_token": "", "enabled": True}
    assert redacted["plugins"]["server"] == {"smtp_password": "", "telnet_password_prompt": "Password:"}
    mcp = redacted["plugins"]["mcp"]["servers"][0]
    assert mcp == {"authorization": "", "env": "", "headers": "", "bearer_token_env_var": "MY_VAR",
                   "tool_timeout_sec": "5"}
    assert redacted["plugins"]["tuya"] == {"tuya_access_token": "", "tuya_token_expire_at": "123",
                                           "tuya_token_get": True}
    assert redacted["app.env"] == {"OPENAI_API_KEY": "", "HOME_DIR": "/home"}
    assert redacted["max_tokens"] == 4096 and redacted["max_output_tokens"] == "2048"
    assert redacted["security.prompt_injection.prompt"] == "token of trust"
    assert count == 12
    # input untouched
    assert CONFIG["api_key"] == "sk-top"


def make_exporter(tmp_path):
    workdir = tmp_path / "profile"
    workdir.mkdir()
    (workdir / "config.json").write_text(json.dumps(CONFIG), encoding="utf-8")
    (workdir / "models.json").write_text(json.dumps({"items": {"m": {"custom_api_key": "k"}}}), encoding="utf-8")
    (workdir / "notes.txt").write_text("api_key=sk-in-a-text-file", encoding="utf-8")
    (workdir / "broken.json").write_text("{not json", encoding="utf-8")
    config = SimpleNamespace(get_user_path=lambda: str(workdir))
    window = SimpleNamespace(core=SimpleNamespace(config=config))
    exporter = ProfileExporter(window)
    exporter.ensure_space = lambda path, required: None
    return exporter, workdir


def read_zip(path):
    with zipfile.ZipFile(path) as z:
        return {name: z.read(name) for name in z.namelist()}


def test_export_profile_redacts_config_by_default(tmp_path):
    exporter, _ = make_exporter(tmp_path)
    dest = str(tmp_path / "out.zip")
    exporter.export_profile(dest, ["config", "files"], app_version="2.9.1")
    files = read_zip(dest)

    meta = json.loads(files["export_meta.json"])
    assert meta["secrets_redacted"] is True
    cfg = json.loads(files["config/config.json"])
    assert cfg["api_key"] == "" and cfg["providers"]["openai"]["api_key"] == ""
    assert cfg["plugins"]["slack"]["enabled"] is True
    models = json.loads(files["config/models.json"])
    assert models["items"]["m"]["custom_api_key"] == ""
    assert files["config/broken.json"] == b"{not json"  # unparsable: copied verbatim
    assert b"sk-in-a-text-file" in files["files/notes.txt"]  # non-config files are not touched
    assert b"sk-openai" not in b"".join(v for k, v in files.items() if k.startswith("config/"))


def test_export_profile_keeps_secrets_when_requested(tmp_path):
    exporter, _ = make_exporter(tmp_path)
    dest = str(tmp_path / "out.zip")
    exporter.export_profile(dest, ["config"], app_version="2.9.1", include_secrets=True)
    files = read_zip(dest)

    assert json.loads(files["export_meta.json"])["secrets_redacted"] is False
    assert json.loads(files["config/config.json"])["providers"]["openai"]["api_key"] == "sk-openai"


def test_export_without_config_section_reports_no_redaction(tmp_path):
    exporter, _ = make_exporter(tmp_path)
    dest = str(tmp_path / "out.zip")
    exporter.export_profile(dest, ["files"], app_version="2.9.1")
    files = read_zip(dest)
    assert json.loads(files["export_meta.json"])["secrets_redacted"] is False
    assert "config/config.json" not in files
