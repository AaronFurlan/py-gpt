#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ================================================== #
# This file is a part of PYGPT package               #
# Website: https://pygpt.net                         #
# GitHub:  https://github.com/szczyglis-dev/py-gpt   #
# MIT License                                        #
# ================================================== #

from types import SimpleNamespace

from pygpt_net.core.render.web.body import Body

PAYLOAD = 'http://x/a.png" onerror="alert(1)'
ESCAPED = 'http://x/a.png&quot; onerror=&quot;alert(1)'


def make_body():
    config = SimpleNamespace(get=lambda k, d=None: d, get_app_path=lambda: "/fake/app")
    filesystem = SimpleNamespace(
        extract_local_url=lambda url, ctx=None: (url, url),
        get_local_url=lambda path, ctx=None: path,
    )
    window = SimpleNamespace(core=SimpleNamespace(config=config, filesystem=filesystem))
    return Body(window)


def test_escape_helper():
    assert Body.escape('<a href="x">&</a>') == "&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;"
    assert Body.escape(None) == ""
    assert Body.escape(5) == "5"


def test_image_html_escapes_url_attributes():
    html = make_body().get_image_html(PAYLOAD, 1, 2)
    assert 'onerror="alert' not in html
    assert f'src="{ESCAPED}"' in html
    assert f'title="{ESCAPED}"' in html
    assert f'href="bridge://open_image/{ESCAPED}"' in html


def test_video_html_escapes_source():
    payload = '/tmp/v.mp4" onerror="alert(1)'
    b = make_body()
    b.window.core.filesystem.extract_local_url = lambda url, ctx=None: (url, "/tmp/v.mp4")
    html = b.get_image_html(payload)
    assert 'onerror="alert' not in html
    assert '<source src="/tmp/v.mp4&quot; onerror=&quot;alert(1)" type="video/mp4">' in html


def test_url_html_escapes_link_and_text():
    html = make_body().get_url_html('http://x/?a=1&b=<s>', 1, 1)
    assert 'href="http://x/?a=1&amp;b=&lt;s&gt;"' in html
    assert '>http://x/?a=1&amp;b=&lt;s&gt;</a>' in html
    assert "<s>" not in html


def test_file_html_escapes_name_and_url():
    b = make_body()
    b.window.core.filesystem.extract_local_url = lambda url, ctx=None: (url, '/d/<img src=x onerror=alert(1)>.txt')
    b.filetype_icon_url = lambda path: "qrc:///filetypes/txt.svg"
    html = b.get_file_html('file:///d/x" onclick="alert(1)', 1, 1)
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;.txt" in html
    assert 'href="file:///d/x&quot; onclick=&quot;alert(1)"' in html


def test_docs_html_escapes_metadata():
    docs = [{'<u>': {'<k>': '<v>&'}}]
    html = make_body().get_docs_html(docs)
    assert "<u>" not in html and "<k>" not in html and "<v>" not in html
    assert "&lt;u&gt;" in html and "<b>&lt;k&gt;:</b> &lt;v&gt;&amp;" in html
