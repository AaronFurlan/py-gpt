#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# ================================================== #

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMessageBox

from tests.mocks import mock_window
from pygpt_net.controller.chat.command import Command
from pygpt_net.core.events import KernelEvent
from pygpt_net.core.security import Security
from pygpt_net.item.ctx import CtxItem

DANGEROUS = [{'cmd': 'shell_exec', 'params': {'command': 'rm -rf /'}}]
HARMLESS = [{'cmd': 'fs_read_file', 'params': {'path': 'a.txt'}}]


def make_command(mock_window, main_thread=True):
    mock_window.core.security = Security(mock_window)
    mock_window.core.plugins.get = MagicMock(return_value=None)
    mock_window.core.config.data['cmd'] = True
    mock_window.core.command.is_enabled = MagicMock(return_value=True)
    mock_window.controller.kernel.stopped = MagicMock(return_value=False)
    mock_window.controller.kernel.is_main_thread = MagicMock(return_value=main_thread)
    mock_window.controller.agent.legacy.is_tool_enabled = MagicMock(return_value=False)
    return Command(mock_window)


def dispatched_tool_call(mock_window) -> bool:
    for call in mock_window.dispatch.call_args_list:
        event = call.args[0] if call.args else None
        if isinstance(event, KernelEvent) and event.name == KernelEvent.TOOL_CALL:
            return True
    return False


def test_handle_pauses_before_dangerous_tool_and_resumes_after_confirmation(mock_window):
    command = make_command(mock_window)
    mock_window.core.command.extract_cmds = MagicMock(return_value=list(DANGEROUS))
    ctx = CtxItem()

    assert command.handle(ctx) is True
    assert command.has_pending_safety_confirmation() is True
    assert command.pending_safety_ctx is ctx
    assert mock_window.ui.dialogs.confirm.called
    assert mock_window.ui.dialogs.confirm.call_args.kwargs['type'] == Command.SAFETY_CONFIRM_TYPE
    msg = mock_window.ui.dialogs.confirm.call_args.kwargs['msg']
    assert 'shell_exec: rm -rf /' in msg
    assert dispatched_tool_call(mock_window) is False
    assert not mock_window.controller.plugins.apply_cmds.called

    # user approves: ctx is marked confirmed and the same ctx is dispatched for execution
    assert command.confirm_pending_safety_confirmation(ctx) is True
    assert mock_window.core.security.is_commands_confirmed(ctx) is True
    assert command.has_pending_safety_confirmation() is False
    assert dispatched_tool_call(mock_window) is True


def test_handle_rejection_stops_request_without_execution(mock_window):
    command = make_command(mock_window)
    mock_window.core.command.extract_cmds = MagicMock(return_value=list(DANGEROUS))
    ctx = CtxItem()
    command.handle(ctx)

    assert command.reject_pending_safety_confirmation(ctx) is True
    assert ctx.extra.get('commands_rejected') is True
    assert mock_window.core.security.is_commands_confirmed(ctx) is False
    assert mock_window.controller.chat.common.stop.called
    assert dispatched_tool_call(mock_window) is False


def test_handle_does_not_pause_for_harmless_tools(mock_window):
    command = make_command(mock_window)
    mock_window.core.command.extract_cmds = MagicMock(return_value=list(HARMLESS))
    ctx = CtxItem()

    assert command.handle(ctx) is True
    assert command.has_pending_safety_confirmation() is False
    assert not mock_window.ui.dialogs.confirm.called
    assert dispatched_tool_call(mock_window) is True


def test_handle_does_not_pause_when_confirmation_disabled(mock_window):
    command = make_command(mock_window)
    mock_window.core.config.data[Security.COMMANDS_CONFIRM_ENABLED_KEY] = False
    mock_window.core.command.extract_cmds = MagicMock(return_value=list(DANGEROUS))
    ctx = CtxItem()

    assert command.handle(ctx) is True
    assert command.has_pending_safety_confirmation() is False
    assert dispatched_tool_call(mock_window) is True


def test_confirm_commands_passes_without_dialog_when_not_required(mock_window, monkeypatch):
    command = make_command(mock_window)
    question = MagicMock(side_effect=AssertionError("dialog must not be shown"))
    monkeypatch.setattr(QMessageBox, "question", question)

    assert command.confirm_commands(CtxItem(), list(HARMLESS)) is True

    ctx = CtxItem()
    mock_window.core.security.mark_commands_confirmed(ctx)
    assert command.confirm_commands(ctx, list(DANGEROUS)) is True


def test_confirm_commands_main_thread_dialog_yes_and_no(mock_window, monkeypatch):
    command = make_command(mock_window, main_thread=True)

    monkeypatch.setattr(QMessageBox, "question", MagicMock(return_value=QMessageBox.StandardButton.No))
    ctx = CtxItem()
    assert command.confirm_commands(ctx, list(DANGEROUS)) is False
    assert ctx.extra.get('commands_rejected') is True

    monkeypatch.setattr(QMessageBox, "question", MagicMock(return_value=QMessageBox.StandardButton.Yes))
    ctx = CtxItem()
    assert command.confirm_commands(ctx, list(DANGEROUS)) is True
    assert mock_window.core.security.is_commands_confirmed(ctx) is True


def test_confirm_commands_returns_false_when_stopped(mock_window, monkeypatch):
    command = make_command(mock_window, main_thread=True)
    mock_window.controller.kernel.stopped = MagicMock(return_value=True)
    monkeypatch.setattr(QMessageBox, "question", MagicMock(side_effect=AssertionError("no dialog")))
    assert command.confirm_commands(CtxItem(), list(DANGEROUS)) is False


def test_confirm_commands_worker_thread_waits_for_dialog_decision(mock_window):
    command = make_command(mock_window, main_thread=False)

    def approve(ctx, resume_callback=None):
        mock_window.core.security.mark_commands_confirmed(ctx)
        resume_callback()

    def deny(ctx, resume_callback=None):
        mock_window.core.security.mark_commands_rejected(ctx)
        resume_callback()

    command.pause_for_safety_confirmation = MagicMock(side_effect=approve)
    ctx = CtxItem()
    assert command.confirm_commands(ctx, list(DANGEROUS)) is True
    assert command.pause_for_safety_confirmation.call_args.args[0] is ctx
    assert ctx.cmds == DANGEROUS

    command.pause_for_safety_confirmation = MagicMock(side_effect=deny)
    assert command.confirm_commands(CtxItem(), list(DANGEROUS)) is False
