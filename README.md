# Sangam Command

A static Leaflet 1.9.4 research atlas for Prayagraj, with the original operations workspace, search, filters, incidents and browser-local records. Geometry is GeoJSON in **EPSG:4326, longitude then latitude**. Leaflet uses Web Mercator for OSM tiles; measurements use UTM zone44N (EPSG:32644).

This is a geographically positioned research foundation, **not a validated crowd simulation or complete official mela map**. All 25 sector identities/boundaries are provisional. The traced footprint is 2,097.7ha rather than the reported 4,000ha. 66 inventory references remain unlocated; their geometry isnull so no invented position enters the graph. All 27 observed pontoon candidates have both approaches attached; the approaches for 01–04 (west) and 06 (east) are low-confidence sandbar traces, and three additional bridge slots have no location. See NOTES.md and data/network/validation.json.

## Run

```sh
python3 scripts/serve_local.py
```

Open http://127.0.0.1:8765. Any static server can serve dist/. There is no frontend build step. Leaflet 1.9.4 loads from cdnjs with a vendored fallback. Six satellite PNGs and cached GeoJSON are local; online OSM background tiles require connectivity. With those tiles unavailable, the satellite and vector layers still work. No OSM bulk tile download is performed.

“Original” opens an unregistered image only on localhost when local-reference/source-map.jpg exists and scripts/serve_local.py serves it. The newspaper PDF/JPG are excluded from Git’s current tree and dist/. The image is never warped or overlaid. The deployable directory is dist/ only.

## Data and provenance

| Dataset | Source and interpretation |
| --- | --- |
| data/osm/ | Cached Overpass snapshot, fetched 2026-10-25. Roads, railways, bridges, stations, permanent police, temples, parking and locality records retain OSM IDs/tags and fetched_at. This is a current OSM snapshot, **not a historical January 2025 OSM reconstruction**. |
| data/mela/sectors.geojson | 25 provisional camp polygons drawn against January27 Sentinel tent blocks/roads, clipped out of water and one another. TOI provides numbering and neighbour order only; assignments require official confirmation. |
| data/mela/river_banks.geojson | Constrained RGB water mask, not NDWI. Dark-green classification plus inspected river corridor; approximate 10–20 m shorelines. Includes the northern extension. |
| data/mela/sangam_nose.geojson | Dry-land destination near the observed Sangam tip, not a surveyed gate. |
| data/mela/mela_roads.geojson and pontoon_approaches.geojson | 28 main road traces and 46 observed approach/shoreline lines. Water portions removed. Width ~5.5 m, measured on Google Maps satellite (chequered-plate mela roads: Kila Ghat Rd 5.4 m, Sangam Marg ~5 m, Annapurna Rd ~5.5 m). |
| data/mela/pontoon_bridges.geojson | 27 observed candidate alignments plus 3 explicitnull inventory slots; IDs are observation references, not official bridge numbers. |
| data/mela/parking.geojson | 36 OSM parking records. These are not asserted to be 2025 mela parking, nor matched arbitrarily to the newspaper’s 33 coloured patches. |
| data/mela/police_temporary.geojson | Empty placeholder pending official UP Police/Mela Authority data. |
| data/mela/reference_inventory.json | Legacy names, stableIDs and historical summary figures, with all newspaper pixel geometry removed. |
| data/network/ | Connected simulation graph, station routes, disconnected candidates and machine-readable audit. |
| dist/map-data.json | App index with stableIDs, GeoJSON geometry, label coordinates, source, confidence and polygon area_ha. nullgeometry means unresolved. |

Source values are osm, traced:sentinel2-2025-01-27 or toi_reference. Confidence is high/medium/low. High OSM confidence indicates an identified source feature, not verified 2025 access. All sector assignments and inferred access edges are low. User-created workspace markers have source:user and remain separate from the canonical source atlas.

The nine stations are deduplicated: Prayagraj Rambagh shows Allahabad City; Daraganj is an alias of Prayagraj Sangam; duplicate Subedarganj representations are excluded. Four named temples are matched in OSM. Six more (Beni Madhav, Samudra Koop, Aadi Veni Madhav, Chakra Madhav, Shankh Madhav, Someshwar) are not in OSM or Wikidata and are placed from Google Maps (data/mela/landmarks_google.geojson, scripts/place_google_landmarks.py). Lankeshwar is not on Google Maps and Gangeshwar has several same-name temples, none at the TOI position; both stay unlocated.

## Satellite preparation and reproducibility

The six supplied RGB GeoTIFFs are in /Users/piyushchauhan/personal-projects/crowd-research/data/sentinel2/: 2024-10-19,2025-01-22,2025-01-27,2025-02-01,2025-02-11,2025-02-21. GDAL reprojects the rasters from EPSG:32644 to EPSG:3857 PNGs with exact transformed pixel-edge bounds. This avoids treating an unwarped UTM rectangle as a WebMercator image. All output vector coordinates are WGS84.

The supplied crop stops near 25.476°N. The same-date public scene S2B_44RNP_20250127_0_L2A supplies another 6 km north, preserving physical coverage of the upper camp. The other five dates retain the original extent. Scene URL and bounds are in data/sentinel2/manifest.json. This extension is reproducible with scripts/fetch_sentinel_extension.py. Native raster pixel vertices in tracing scripts refer only to Sentinel’s affine transform, never TOI pixels.

Data regeneration requires GDAL command-line tools plus Python dependencies in scripts/requirements.txt. It is separate from running the static app:

```sh
python3 -m venv .venv
.venv/bin/pip install -r scripts/requirements.txt
.venv/bin/python scripts/fetch_osm.py --refresh
.venv/bin/python scripts/normalize_osm.py
.venv/bin/python scripts/fetch_sentinel_extension.py
.venv/bin/python scripts/prepare_sentinel.py
.venv/bin/python scripts/trace_water.py
.venv/bin/python scripts/trace_mela.py
.venv/bin/python scripts/trace_pontoons.py
.venv/bin/python scripts/trace_pontoon_approaches.py
.venv/bin/python scripts/build_network.py
.venv/bin/python scripts/validate_geo.py
.venv/bin/python scripts/validate_network.py
.venv/bin/python scripts/merge_data.py
.venv/bin/python scripts/package_network.py
node tests/validate.mjs
```

fetch_osm.py uses the requested Overpass endpoint/bbox and a User-Agent. Omit --refresh to reuse the cached raw response. Normalization currently pins the reviewed OSM IDs; a future snapshot that deletes/replaces them requires review. No Google Maps/Places data is used. Supplied raw GeoTIFFs, the downloaded extension, and the local newspaper are ignored. Cached normalized data and processed overlays are included.

## Walking graph

nodes.geojson, edges.geojson and graph.graphml contain the single Sangam-connected component: 102,241 nodes and 111,352 edges. All 9 station points, 36 OSM parking representatives and 25 sector representatives are reachable. Detached OSM/trace components remain in disconnected_nodes.geojson/disconnected_edges.geojson and the full-network audit, without fictitious connecting roads. Browser render_edges.geojson includes all candidates, so it is a visualization rather than the canonical graph.

OSM shared nodeIDs preserve grade separation. Temporary line crossings are joined only to eligible ground roads; bridge/road endpoints snap within 30 m with no water-crossing access links. Station/parking/sector access connects to a nearby reachable road node, avoiding the water mask. Access edges are inferred straight links, not surveyed paths or entrances; connectors over 100 m are flagged. Sector representative-point reachability does not establish that its entire polygon is walkable. OSM access restrictions are screened; real operating restrictions and 2025 closures are unknown.

Edges retain length_m, kind (osm_road,mela_road,pontoon,access), approx_width_m with width_source (osm_width_tag, osm_lanes, osm_class_default, google_maps_measured, estimate) and width_confidence, source, confidence and original sourceIDs. Routes use Dijkstra by length and are checked for continuity and edge-length agreement. Prayagraj Sangam is closest at 2.36 km; Phaphamau is 12.57 km. Widths are approximate: OSM width/lanes tags where present, otherwise typical Indian widths per highway class; pontoon decks are an unpublished-spec estimate of 5 m. Measured widths, obstacle polygons, gate geometry and dynamic bridge rules are still required before creating a valid JuPedSim walkable domain.

The large uncompressed node/edge/GraphML files remain locally generated. Source & inventory offers dist/data/network/network.zip (about 15 MB), containing these exports and their audit. Extract it to recover the uncompressed files without installing GIS tools.

## Workspace compatibility

The localStorage key remains sangam-command-workspace-v1. Schema 1 records migrate to schema 2. The old value is backed up once under sangam-command-workspace-v1-backup-before-geographic-v2. All 108 legacy featureIDs remain in the index. Sector updates and incidents stay attached to their IDs. Legacy marker pixel locations are preserved in legacy_location; they are not assigned fictitious longitude/latitude. Use “Place / move on map” to locate them. Import accepts both schema versions and validates canonical feature links and geographic bounds. Export includes the workspace, not the entire graph archive.

## Verification

Run node tests/validate.mjs, python scripts/validate_geo.py and python scripts/validate_network.py with the appropriate runtimes. Checks cover legacyID retention, workspace migration and validation, coordinate bounds/provenance, absent deployable TOI assets, valid/disjoint/water-free sectors, station proximity to railways, serialized graph connectivity, and all 9 shortest routes. The “all observed pontoon endpoints connected” check passes; five of those connections rely on low-confidence sandbar approach traces.

Browser QA verified satellite date changes, baseline comparison, low-confidence filtering, station route display, graph rendering, zero-count persistence after reload, and validated workspace import. qa/sangam-nose.png and qa/jhusi-side.png record visual inspection. These show 10 m imagery, not survey-scale detail.

## Attribution and licences

- © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). OSM-derived databases/graph exports retain attribution and applicable share-alike obligations.
- Contains modified Copernicus Sentinel data 2024–2025. See [Copernicus Sentinel data legal notice](https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice).
- [Leaflet 1.9.4](https://leafletjs.com/), BSD 2-Clause; CDN and local fallback retain upstream copyright notices.
- TOI, Lucknow reference supplied by the user: sector numbering/topology and historical figures only. The newspaper images are not distributed.
- Code is MIT-licensed (see `LICENSE`). Data derived from OpenStreetMap stays under ODbL and Sentinel data under the Copernicus terms above; the MIT licence does not override them.
- This is hobby research, not an operational safety system. Widths, routes and traced geometry are approximate.
