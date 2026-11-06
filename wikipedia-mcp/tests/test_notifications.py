import pytest

from server import notify


class FakeContext:
    def __init__(self):
        self.logs = []
        self.progress = []

    async def info(self, message):
        self.logs.append(message)

    async def report_progress(self, progress, total, message):
        self.progress.append((progress, total, message))


@pytest.mark.asyncio
async def test_notify_sends_log_and_progress():
    ctx = FakeContext()

    await notify(ctx, 40, "Retrieved 2 Wikipedia article(s).")

    assert ctx.logs == ["Retrieved 2 Wikipedia article(s)."]
    assert ctx.progress == [
        (40, 100, "Retrieved 2 Wikipedia article(s).")
    ]
