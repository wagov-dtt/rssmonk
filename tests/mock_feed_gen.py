from fastapi import FastAPI
from fastapi.responses import Response
import random
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import uuid


# Fixed list of guid for testing
guid_list = ["0209399a-8fc8-4034-86d0-a8423000",
             "87bad491-5bec-490b-b16a-defde001",
             "34b3e3aa-0975-4ff8-baf0-dd07d002",
             "bf8a8103-3320-4130-9e2d-8a8f4003",
             "e72dca4e-4c8e-4fe4-9b86-6ebe1004",
             "74184377-12d8-4f15-a6dd-7aa0a005",
             "191dcbc3-e162-4531-bffd-60e69006",
             "5a94d86a-26f4-49c4-a500-1f370007"]

external_app = FastAPI()

@external_app.get("/feed-{x}")
async def ping(x: int):
    return Response(content=make_media_statements_feed(x), media_type="application/xml; charset=utf-8")


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
    portfolio_list = ["Treasurer", "Health", "Transport"]
    portfolio_code = ["portfolio 143", "portfolio 3", "portfolio 345"]
    region_list = ["Central", "North", "East", "South", "West"]
    region_code = ["region 100", "region 223", "region 323", "region 473", "region 522"]

    # Create the channel element
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Media Statements"
    ET.SubElement(channel, "link").text = f"https://www.localhost:10000/feed-{items}"
    ET.SubElement(channel, "description").text = "Government media statements from the government."
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(channel, "atom:link", {
        "href": f"https://www.localhost:10000/feed-{items}",
        "rel": "self",
        "type": "application/rss+xml"
    })

    # Generate multiple items with advancing pubDate. Order of items is permitted per RSS spec
    base_date = datetime.now() - timedelta(minutes=(5*items + 2))
    for i in range(items):
        email_minister_str = ""
        email_ident_str = ""
        email_portfolio_str = ""
        email_region_str = ""
        if i < len(minister_list):
            email_minister_str = minister_list[i]
            email_portfolio_str = portfolio_list[i]
            email_region_str = region_list[i]
            email_ident_str = minister_code[i] + "," + portfolio_code[i] + "," + region_code[i]
        else:
            email_minister_str = ", ".join(minister_list)
            email_portfolio_str = ", ".join(portfolio_list)
            email_region_str = ", ".join(region_list)
            email_ident_str = ",".join(minister_code + portfolio_code + region_code)

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"Title number {i + 1}"
        ET.SubElement(item, "link").text = f"hhttps://www.localhost:10000/rss/media-statements/project-update-{i+1}"
        ET.SubElement(item, "description").text = (
            f"Description number {i}\n"
            f"Published: {base_date.strftime('a, %d %b %Y %H:%M:%S +0800')}\n"
            f"Minister: {email_minister_str}\n"
            f"Portfolio: {email_portfolio_str}\n"
            f"Regions: {email_region_str}\n"
        )
        ET.SubElement(item, "pubDate").text = base_date.strftime('a, %d %b %Y %H:%M:%S +0800')
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = guid_list[i]
        ET.SubElement(item, "wa:subject_entities").text = email_minister_str
        ET.SubElement(item, "wa:identifiers").text = f"{email_ident_str},region 8635"
        base_date += timedelta(minutes=5)

    return prettify(rss)


# Convert to pretty XML string
def prettify(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


if __name__ == "__main__":
    #print(make_media_statements_feed(random.randint(1, 4)))
    import uvicorn
    uvicorn.run(external_app, port=10000, log_level="info")
