from fastapi import FastAPI
import random
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import uuid


external_app = FastAPI()

@external_app.get("/feed-{x}")
async def ping(x: int):
    return make_media_statements_feed(x)


# Only need to make a few items over a few minutes, or days for testing purposes
# Edited from CoPilot output for feed generation
def make_media_statements_feed(items: int) -> str:
    if items > 4: # Only support 4 items that can be created for the return feed
        items = 4

    # Create the root RSS element
    rss = ET.Element("rss", {
        "version": "2.0",
        "xmlns:wa": "https://www.wa.gov.au/rss/media-statements",
        "xmlns:dc": "http://purl.org/dc/elements/1.1/",
        "xmlns:atom": "http://www.w3.org/2005/Atom"
    })

    # Randomised lists to generate different categories
    minister_list = ["Hon. Premier MLA", "Hon. Senior Minister MLA", "Hon. Minister MLA"]
    minister_code = ["minister 0", "minister 1", "minster 2"]
    portfolio_list = ["Treasurer", "Health", "Transport, Planning and Lands"]
    portfolio_code = ["portfolio 143", "portfolio 3", "portfolio 345"]

    # Create the channel element
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Media Statements"
    ET.SubElement(channel, "link").text = "https://www.wa.gov.au/rss/media-statements"
    ET.SubElement(channel, "description").text = "Western Australian government media statements from the WA Government."
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(channel, "atom:link", {
        "href": "https://www.wa.gov.au/rss/media-statements",
        "rel": "self",
        "type": "application/rss+xml"
    })

    # Generate multiple items with advancing pubDate. Order of items is permitted per RSS spec
    base_date = datetime.now() - timedelta(minutes=(5*items + 2))
    for i in range(items):
        email_minister_str = ""
        email_ident_str = ""
        email_portfolio_str = ""
        if i < len(minister_list):
            email_minister_str = minister_list[i]
            email_portfolio_str = portfolio_list[i]
            email_ident_str = minister_code[i] + "," + portfolio_list[i]
        else:
            email_minister_str = ", ".join(minister_list)
            email_portfolio_str = ", ".join(portfolio_list)
            email_ident_str = ",".join(minister_code + portfolio_code)

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"Title number {i + 1}"
        ET.SubElement(item, "link").text = f"https://www.wa.gov.au/government/media-statements/project-update-{i+1}"
        ET.SubElement(item, "description").text = (
            f"Description number {i}"
            f"Published: {base_date.strftime('%a, %d %b %Y %H:%M:%S +0800')}"
            f"Minister: {email_minister_str}"
            f"Portfolio: {email_portfolio_str}"
            "Regions: Perth Metro"
        )
        ET.SubElement(item, "pubDate").text = base_date.strftime('%a, %d %b %Y %H:%M:%S +0800')
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = str(uuid.uuid4())[0:(32-3)] + f"{i}".zfill(3)
        ET.SubElement(item, "wa:subject_entities").text = email_minister_str
        ET.SubElement(item, "wa:identifiers").text = f"{email_ident_str},region 8635"
        base_date += timedelta(minutes=5)

    return prettify(rss)


# Convert to pretty XML string
def prettify(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ",newl="")


if __name__ == "__main__":
    #print(make_media_statements_feed(random.randint(1, 4)))
    import uvicorn
    uvicorn.run(external_app, port=10000, log_level="info")
