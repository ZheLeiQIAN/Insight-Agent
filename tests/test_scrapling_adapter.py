"""Scrapling optional integration tests."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawlers.common import scrapling_adapter


def test_scrapling_status_shape():
    status = scrapling_adapter.get_status()
    assert isinstance(status.available, bool)
    assert isinstance(status.reason, str)


def test_extract_page_summary_with_fake_page():
    class FakeSelection:
        def __init__(self, values):
            self.values = values

        def get(self):
            return self.values[0] if self.values else ""

        def getall(self):
            return self.values

    class FakePage:
        def css(self, selector):
            if selector == "title::text":
                return FakeSelection(["Demo Title"])
            if "h1" in selector:
                return FakeSelection(["Heading"])
            if selector == "p::text":
                return FakeSelection(["Paragraph one", "Paragraph two"])
            return FakeSelection([])

    summary = scrapling_adapter.extract_page_summary(FakePage())
    assert summary["title"] == "Demo Title"
    assert summary["headings"] == ["Heading"]
    assert summary["paragraphs"] == ["Paragraph one", "Paragraph two"]
