#!/usr/bin/env python3
"""Refresh the static parade feed and geocode its unique locations."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FEED_URL = "https://www.paradescommission.org/Home.aspx?rss=UpcomingParades"
GEOCODER_URL = "https://photon.komoot.io/api/"
USER_AGENT = "cq3-parade-map/1.0 (https://github.com/pjmclaughlin1979/cq3)"
LOCATION_PATTERN = re.compile(
    r"Location:\s*(.*?)\s*(?=<br\b|Outward Route:|$)", re.IGNORECASE | re.DOTALL
)
PLACE_TYPES = {"city", "town", "village", "hamlet", "suburb", "borough"}


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def item_text(item: ET.Element, name: str) -> str:
    element = item.find(name)
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def parse_feed(xml: bytes) -> tuple[list[dict], str | None]:
    root = ET.fromstring(xml)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("The parade RSS feed has no channel element")

    parsed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pub_dates = [
        parsedate_to_datetime(value).astimezone(timezone.utc)
        for item in channel.findall("item")
        if (value := item_text(item, "pubDate"))
    ]
    if pub_dates:
        parsed_at = max(pub_dates).isoformat(timespec="seconds")

    parades = []
    for item in channel.findall("item"):
        title = re.sub(r"^##\s*(.*?)\s*##$", r"\1", item_text(item, "title"))
        date_value = item_text(item, "paradedate")
        date = None
        if date_value:
            for date_format in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
                try:
                    date = datetime.strptime(date_value, date_format).date().isoformat()
                    break
                except ValueError:
                    continue
        if not title or date is None:
            continue

        description = item_text(item, "description")
        location_match = LOCATION_PATTERN.search(description)
        location = re.sub(r"\s+", " ", location_match.group(1)).strip() if location_match else ""
        link = item_text(item, "link")
        parsed_link = urllib.parse.urlparse(link)
        if parsed_link.hostname and parsed_link.hostname.endswith("paradescommission.org"):
            link = urllib.parse.urlunparse(
                ("https", parsed_link.netloc, parsed_link.path, "", parsed_link.query, "")
            )
        else:
            link = ""

        identity = link or hashlib.sha256(
            f"{title}|{date}|{location}".encode("utf-8")
        ).hexdigest()
        times = re.split(r"\s+to\s+", item_text(item, "outwardtimes"), maxsplit=1, flags=re.I)
        parades.append(
            {
                "id": identity,
                "title": title,
                "date": date,
                "startTime": times[0].strip() if times else "",
                "endTime": times[1].strip() if len(times) > 1 else "",
                "location": location,
                "route": item_text(item, "outwardroute"),
                "returnRoute": item_text(item, "returnroute"),
                "contentious": item_text(item, "contentious").casefold() == "true",
                "link": link,
            }
        )
    return parades, parsed_at


def geocode(location: str) -> dict | None:
    query = urllib.parse.urlencode(
        {
            "q": f"{location}, Northern Ireland, United Kingdom",
            "limit": 10,
            "lang": "en",
        }
    )
    response = json.loads(fetch(f"{GEOCODER_URL}?{query}"))
    features = response.get("features", [])
    place = next(
        (
            feature
            for feature in features
            if feature.get("properties", {}).get("osm_key") == "place"
            and feature.get("properties", {}).get("osm_value") in PLACE_TYPES
        ),
        None,
    )
    if place is None and features:
        place = features[0]
    if place is None:
        return None

    longitude, latitude = place["geometry"]["coordinates"]
    properties = place.get("properties", {})
    return {
        "latitude": latitude,
        "longitude": longitude,
        "label": properties.get("name") or location,
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    cache_path = DATA_DIR / "parade-geocodes.json"
    feed_path = DATA_DIR / "parades.json"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    parades, published_at = parse_feed(fetch(FEED_URL))

    locations = sorted({parade["location"] for parade in parades if parade["location"]})
    new_locations = [location for location in locations if location not in cache]
    for index, location in enumerate(new_locations):
        if index:
            time.sleep(1)
        cache[location] = geocode(location)
        print(f"Geocoded {location}: {'found' if cache[location] else 'no match'}")

    for parade in parades:
        parade["coordinates"] = cache.get(parade["location"])

    write_json(cache_path, cache)
    write_json(
        feed_path,
        {
            "source": FEED_URL,
            "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "feedPublishedAt": published_at,
            "parades": parades,
        },
    )
    located = sum(parade["coordinates"] is not None for parade in parades)
    print(f"Updated {len(parades)} parades; {located} have geocoded locations.")


if __name__ == "__main__":
    main()
