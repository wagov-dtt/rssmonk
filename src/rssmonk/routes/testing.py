"""Test routes for integration testing - not included in production API docs."""

from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from xml.dom import minidom

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(prefix="/test", tags=["testing"], include_in_schema=False)


@router.get("/feed")
async def test_feed(items: int = 3):
    """Generate dynamic test RSS feed for integration testing."""
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Test Feed"
    ET.SubElement(channel, "link").text = "http://localhost:8000/test/feed"
    ET.SubElement(channel, "description").text = "Test RSS feed for integration testing"

    base_date = datetime.now() - timedelta(hours=items)
    for i in range(min(items, 10)):
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"Test Article {i + 1}"
        ET.SubElement(item, "link").text = f"http://example.com/article-{i + 1}"
        ET.SubElement(item, "description").text = f"Description for test article {i + 1}"
        ET.SubElement(item, "guid").text = f"test-guid-{i + 1}"
        ET.SubElement(item, "pubDate").text = base_date.strftime("%a, %d %b %Y %H:%M:%S +0000")
        base_date += timedelta(hours=1)

    xml_str = minidom.parseString(ET.tostring(rss, "utf-8")).toprettyxml(indent="  ")
    return Response(content=xml_str, media_type="application/rss+xml")
