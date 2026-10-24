# Northern Ireland Parade Map

**Live site:** https://pjmclaughlin1979.github.io/northern-ireland-parade-map/

An interactive map of upcoming parades and processions in Northern Ireland.
It uses React, the ArcGIS Maps SDK for JavaScript 5.1 and a glass-style event
sidebar. Select a parade to zoom to it and show matching OpenStreetMap streets
as a translucent route overlay. At closer map zooms, nearby parade streets are
also matched and displayed.

## How the information is populated

The map is a static site, so it does not request the RSS feed directly from a
visitor's browser. The Parade Commission RSS endpoint does not allow those
cross-origin browser requests. Instead, a scheduled GitHub Actions workflow
runs `tools/update_parades.py` daily (and can be started with **Actions →
Update parade map data → Run workflow**):

1. The updater fetches the upcoming-parades RSS feed from
   <https://www.paradescommission.org/Home.aspx?rss=UpcomingParades>.
2. It extracts each parade's title, date, start and end times, location,
   outward and return routes, contentious flag, and source-detail link.
3. It geocodes each distinct location once with Photon, using the location
   town or area rather than pretending the feed supplies an exact route
   geometry. Results are reused from `data/parade-geocodes.json`; only new
   locations are looked up, with a one-second pause between lookups.
4. It writes the parade records and coordinates to `data/parades.json`.
   Both generated JSON files are committed to the repository so the static
   page can load them without a server or API key. A missing location match is
   retained without a map pin rather than assigned a fabricated coordinate.
5. The commit triggers the GitHub Pages deployment workflow, which republishes
   `index.html` and the data files.

The feed provides route streets as text, not as a mapped path. When a user
selects a parade, the page searches OpenStreetMap Nominatim for each named
street in that parade's locality and draws returned street geometry. When the
map is zoomed in, nearby named roads are fetched from the Overpass API and
matched against visible parades' route text. Street lookups are rate-limited
and cached for the current page session. Routes are approximate: a street name
may match multiple road segments, and unmatched names or unmapped roads are
omitted. The overlay is not an official parade route.

## Data sources and attribution

- Parade details: [Parades Commission RSS feed](https://www.paradescommission.org/Home.aspx?rss=UpcomingParades)
- Town geocoding: [Photon](https://github.com/komoot/photon), based on OpenStreetMap
- Street geometry: [OpenStreetMap](https://www.openstreetmap.org/copyright), queried through [Nominatim](https://nominatim.org/) and [Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API)
- Map basemap and SDK: Esri ArcGIS Maps SDK for JavaScript 5.1

## Refreshing data locally

Run Python 3 from the repository root:

```sh
python3 tools/update_parades.py
```

The updater requires network access to the RSS feed and Photon. It writes
`data/parades.json` and updates the geocoding cache in
`data/parade-geocodes.json`.

To preview the site locally, serve the repository over HTTP (for example,
`python3 -m http.server 8000`) and open <http://localhost:8000/>.
