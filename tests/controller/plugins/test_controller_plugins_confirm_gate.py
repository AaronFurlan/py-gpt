#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# ================================================== #

from unittest.mock import MagicMock

from tests.mocks import mock_window
from pygpt_net.controller import Plugins
from pygpt_net.item.ctx import CtxItem

CMDS = [{'cmd': 'shell_exec', 'params': {'command': 'ls'}}, {'cmd': 'fs_read_file', 'params': {}}]


def make_plugins(mock_window, allowed: bool):
    plugins = Plugins(mock_window)
    mock_window.core.command.from_commands = MagicMock(side_effect=lambda cmds: list(cmds))
    mock_window.controller.chat.command.confirm_commands = MagicMock(return_value=allowed)
    mock_window.ui.get_status = MagicMock(return_value="")
    return plugins


def test_rejected_commands_are_not_dispatched(mock_window):
    plugins = make_plugins(mock_window, allowed=False)
    ctx = CtxItem()

    results = plugins.apply_cmds(ctx, list(CMDS))

    assert not mock_window.controller.command.dispatch.called
    assert results == ctx.results
    assert [r['request']['cmd'] for r in results] == ['shell_exec', 'fs_read_file']
    assert all(r['result'] == 'Execution rejected by user.' for r in results)
    mock_window.controller.chat.command.confirm_commands.assert_called_once()
    assert mock_window.controller.chat.command.confirm_commands.call_args.args[0] is ctx


def test_confirmed_commands_are_dispatched_and_confirmation_consumed(mock_window):
    plugins = make_plugins(mock_window, allowed=True)
    ctx = CtxItem()

    plugins.apply_cmds(ctx, list(CMDS))

    assert mock_window.controller.command.dispatch.called
    mock_window.core.security.clear_commands_confirmation.assert_called_once_with(ctx)


def test_inline_commands_use_the_same_gate(mock_window):
    plugins = make_plugins(mock_window, allowed=False)
    ctx = CtxItem()

    plugins.apply_cmds_inline(ctx, list(CMDS))

    assert not mock_window.controller.command.dispatch.called
    assert ctx.results[0]['result'] == 'Execution rejected by user.'
