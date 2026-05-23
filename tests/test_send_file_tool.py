import asyncio
import base64

from bot_tools import SendFileTool
from bot_tools import ShellTool


class FakeMessage:
    def __init__(self):
        self.files = []
        self.replies = []

    async def reply(self, content=None, file=None, **kwargs):
        self.replies.append(content)
        if file is not None:
            self.files.append(file)


def test_send_file_tool_sends_text_file():
    tool = SendFileTool(bot=None)
    message = FakeMessage()

    async def run():
        result = await tool.execute(message, filename="hello.py", content="print('hi')\n")
        assert result == "__FILE_SENT__ Sent file: hello.py (12 bytes)"
        assert len(message.files) == 1
        sent = message.files[0]
        assert sent.filename == "hello.py"
        sent.fp.seek(0)
        assert sent.fp.read() == b"print('hi')\n"

    asyncio.run(run())


def test_send_file_tool_sends_base64_and_strips_path():
    tool = SendFileTool(bot=None)
    message = FakeMessage()
    payload = base64.b64encode(b"\x00\x01binary").decode("ascii")

    async def run():
        result = await tool.execute(message, filename="../data.bin", content=payload, encoding="base64")
        assert result == "__FILE_SENT__ Sent file: data.bin (8 bytes)"
        sent = message.files[0]
        assert sent.filename == "data.bin"
        sent.fp.seek(0)
        assert sent.fp.read() == b"\x00\x01binary"

    asyncio.run(run())


def test_shell_tool_runs_without_author_gate():
    tool = ShellTool(bot=None)
    message = FakeMessage()

    async def run():
        result = await tool.execute(message, command="printf hi")
        assert result == "__SHELL_SENT__\n$ printf hi\nhi"
        assert len(message.files) == 0

    asyncio.run(run())
