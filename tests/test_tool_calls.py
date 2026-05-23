from bot import collect_tool_calls


TOOLS = {"react", "web_search", "create_poll"}


def test_collect_tool_calls_accepts_plain_json_tool_object():
    calls = collect_tool_calls('{"tool":"react","emoji":"catjam"}', TOOLS)

    assert [(name, params) for _start, _end, name, params in calls] == [("react", {"emoji": "catjam"})]


def test_collect_tool_calls_accepts_args_object():
    calls = collect_tool_calls('{"tool":"web_search","args":{"query":"openrouter"}}', TOOLS)

    assert [(name, params) for _start, _end, name, params in calls] == [("web_search", {"query": "openrouter"})]


def test_collect_tool_calls_accepts_tool_line_format():
    calls = collect_tool_calls('TOOL react {"emoji":"catjam"}', TOOLS)

    assert [(name, params) for _start, _end, name, params in calls] == [("react", {"emoji": "catjam"})]


def test_collect_tool_calls_keeps_legacy_bracket_format():
    calls = collect_tool_calls('[react]\n{"emoji":"catjam"}\n[/react]', TOOLS)

    assert [(name, params) for _start, _end, name, params in calls] == [("react", {"emoji": "catjam"})]


def test_collect_tool_calls_ignores_disabled_tools():
    calls = collect_tool_calls('{"tool":"react","emoji":"catjam"}', TOOLS, {"react"})

    assert calls == []
