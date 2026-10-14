#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# ================================================== #

from types import SimpleNamespace
from unittest.mock import MagicMock

from pygpt_net.core.security import Security


def make_security(values=None, custom_cmds=None):
    values = dict(values or {})

    def get(key, default=None):
        return values.get(key, default)

    config = SimpleNamespace(get=MagicMock(side_effect=get))
    plugin = SimpleNamespace(get_option_value=MagicMock(return_value=custom_cmds or []))
    plugins = SimpleNamespace(get=MagicMock(return_value=plugin))
    window = SimpleNamespace(core=SimpleNamespace(config=config, plugins=plugins))
    return Security(window)


def test_default_list_covers_dangerous_tools_only():
    sec = make_security()
    assert sec.is_command_confirmation_enabled() is True
    for name in ("shell_exec", "python_exec", "fs_delete_file", "fs_rmdir", "mouse_click",
                 "keyboard_type", "win_keys_send", "srv_exec", "open_web_browser"):
        assert sec.requires_command_confirmation(name) is True, name
    for name in ("fs_read_file", "fs_list_dir", "get_screenshot", "get_mouse_position",
                 "web_search", "wait", "", None):
        assert sec.requires_command_confirmation(name) is False, name


def test_patterns_from_config_support_wildcards():
    sec = make_security({Security.COMMANDS_CONFIRM_LIST_KEY: "fs_*; Custom_Tool"})
    assert sec.requires_command_confirmation("fs_read_file") is True
    assert sec.requires_command_confirmation("custom_tool") is True
    assert sec.requires_command_confirmation("shell_exec") is False

    sec = make_security({Security.COMMANDS_CONFIRM_LIST_KEY: "*"})
    assert sec.requires_command_confirmation("anything") is True

    sec = make_security({Security.COMMANDS_CONFIRM_LIST_KEY: ""})
    assert sec.requires_command_confirmation("shell_exec") is False


def test_custom_plugin_commands_always_require_confirmation():
    sec = make_security({Security.COMMANDS_CONFIRM_LIST_KEY: ""},
                        custom_cmds=[{"name": "deploy_prod"}, {"name": ""}, "junk"])
    assert sec.requires_command_confirmation("deploy_prod") is True
    assert sec.requires_command_confirmation("other") is False


def test_custom_plugin_lookup_failure_is_ignored():
    sec = make_security({Security.COMMANDS_CONFIRM_LIST_KEY: ""})
    sec.window.core.plugins.get = MagicMock(side_effect=RuntimeError("boom"))
    assert sec.requires_command_confirmation("deploy_prod") is False


def test_should_halt_commands_respects_switch_and_confirmation():
    cmds = [{"cmd": "fs_read_file", "params": {}}, {"cmd": "shell_exec", "params": {"command": "ls"}}]
    ctx = SimpleNamespace(extra={}, cmds=cmds)

    sec = make_security()
    assert sec.should_halt_commands(ctx) is True
    assert sec.should_halt_commands(ctx, [{"cmd": "fs_read_file"}]) is False
    assert sec.should_halt_commands(None) is False

    sec.mark_commands_confirmed(ctx)
    assert sec.is_commands_confirmed(ctx) is True
    assert sec.should_halt_commands(ctx) is False
    sec.clear_commands_confirmation(ctx)
    assert sec.is_commands_confirmed(ctx) is False
    assert sec.should_halt_commands(ctx) is True

    sec.mark_commands_rejected(ctx)
    assert ctx.extra.get("commands_rejected") is True
    assert sec.is_commands_confirmed(ctx) is False

    sec = make_security({Security.COMMANDS_CONFIRM_ENABLED_KEY: False})
    assert sec.should_halt_commands(ctx) is False


def test_confirmation_messages_preview_parameters():
    sec = make_security()
    cmds = [
        {"cmd": "shell_exec", "params": {"command": "rm   -rf\n /tmp/x"}},
        {"cmd": "python_exec", "params": {"code": "x" * 300}},
        {"cmd": "mouse_click", "params": {"x": 1, "y": 2}},
        {"cmd": "fs_delete_file"},
        {"cmd": "fs_read_file", "params": {"path": "a.txt"}},
    ]
    lines = sec.get_command_confirmation_messages(cmds)
    assert lines[0] == "shell_exec: rm -rf /tmp/x"
    assert lines[1].startswith("python_exec: " + "x" * 200) and lines[1].endswith("...")
    assert lines[2] == 'mouse_click: {"x": 1, "y": 2}'
    assert lines[3] == "fs_delete_file"
    assert len(lines) == 4
    assert sec.get_command_confirmation_messages(None) == []
