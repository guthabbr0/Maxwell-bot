from bot import MaxwellBot


def test_split_response_closes_and_reopens_code_fence_when_chunking():
    text = "```python\n" + ("print('x')\n" * 80) + "```"

    chunks = MaxwellBot._split_response(text, limit=180)

    assert len(chunks) > 1
    assert all(len(c) <= 188 for c in chunks)
    assert all(c.count("```") % 2 == 0 for c in chunks)


def test_split_response_preserves_custom_filename_extensions_in_code_fence():
    text = "```lol.html\n" + ("<p>hey</p>\n" * 70) + "```"

    chunks = MaxwellBot._split_response(text, limit=170)

    assert len(chunks) > 1
    assert chunks[0].startswith("```lol.html")
    assert all(c.count("```") % 2 == 0 for c in chunks)
