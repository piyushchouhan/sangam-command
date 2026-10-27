# Geospatial migration notes

## Step 0 — audit before changes

The existing published application is a buildless static page. The UI has an atlas directory, search/filter chips, layer toggles, a feature detail panel, sector counts/capacities/team/status forms, an operations table, incidents, and local JSON import/export.

Files: `dist/index.html` (UI), `dist/styles.css` (styling), `dist/app.js` (custom SVG renderer and browser-local operations), `dist/map-data.json` (source inventory), `dist/assets/source-map.pdf` and `source-map.jpg` (newspaper assets), `tests/validate.mjs`, and `README.md`. The Site identity is in `.openai/hosting.json`.

All 108 mapped features use the TOI graphic's image coordinates: the declared canvas is 1284 × 2000, origin top-left, `georeferenced=false`. Each feature has `xy`; sectors and parking have `polygon`; crossings have `line`. There is no longitude/latitude anywhere in this inventory. The SVG background additionally hardcodes river shapes and road-like lines in the same image coordinates.

Inventory: 25 sectors; 9 station points; 12 temple/landmark points; 6 approach points; 5 locality/road labels; 3 water features; 2 regional parking summaries; 13 crossing traces; 33 colour-derived parking envelopes. Sector boundaries were manually traced from the graphic; parking envelopes were segmented from the red/green newspaper patches. Every station/temple position was diagrammatic. Neither the newspaper's geometry nor its drawn road connections is suitable as geographic ground truth.

Storage: key `sangam-command-workspace-v1`; sectors and incidents attach to stable feature IDs. Custom user markers also use image `xy`. Migration must retain those records without silently treating their pixel positions as longitude/latitude. The original records will be backed up, and legacy markers will need explicit replacement on the geographic map.

Source inputs found locally: six Sentinel-2 RGB GeoTIFFs and previews under `data/` (not `data/sentinel2/` in this checkout). Main reference is 2025-01-27, 1315 × 951 pixels at 10 m, EPSG:32644; origin easting 582420, northing 2817890. The user's canonical Sentinel-2 directory will be checked before processing.

No defensible metre-based old/new displacement exists for the old graphic, because it has no geographic transform and the user explicitly prohibits georeferencing it. The comparison will retain this limitation rather than manufacture station errors or median shifts. An unwarped local-only reference can support a visual/topological comparison.

## Progress and verification

Implementation and data-processing results will be appended here with measured checks, provenance and remaining uncertainties.

## Implementation and measured results — 26 October 2026

Leaflet 1.9.4 now replaces the custom SVG engine, with cdnjs and a bundled offline fallback. All rendered geometry is real WGS84 longitude/latitude. Existing panels, filters, sector operations, incidents, marker tools and JSON import/export remain. All 108 original feature IDs survive. Schema 1 workspace data is backed up and migrated; old image markers remain unlocated until manually repositioned.

The OSM snapshot was fetched on 25 October 2026, not January 2025. Nine reviewed stations are deduplicated; 15 permanent police records and four named temple matches are mapped. Six further temples are placed from Google Maps because OSM and Wikidata lack them; Lankeshwar and Gangeshwar remain unmatched. The 36 OSM parking records are not equated with the original 33 newspaper parking patches. Google Maps is used only for those six temple positions and for the mela road width measurement.

The six input rasters were confirmed in the user's canonical Sentinel directory. GDAL reprojected them to Web Mercator PNGs with exact edge bounds. The January 27 image additionally covers 6 km north using scene S2B_44RNP_20250127_0_L2A from the public Sentinel COG collection. Other dates retain their supplied extent. Source URL/bounds are recorded in the manifest.

River extraction uses constrained RGB classification, not a multispectral index. Sector polygons follow inspected camp grids and roads, with water and prior-sector overlaps removed. All sector assignments are explicitly low-confidence hypotheses. The total is 2,097.711 ha, only about 52% of the reported 4,000 ha event extent. The supplied imagery and schematic numbering do not establish the entire official event boundary; inflating polygons to hit the target would invent geometry. Measured pairwise sector overlap and sector/water overlap are both zero square metres. Original WGS84 polygons are valid; UTM reprojection roundoff is repaired before metric overlap calculation.

The map index contains 124 located features and 66 null-geometry references. These 66 include 63 unmatched legacy records and three unknown bridge inventory slots. They retain provenance and stable IDs; they are listed as unlocated and excluded from routing. Thus the request for a real coordinate on every original feature remains unmet where no independently identified location exists.

## Walking network checks

The canonical node/edge/GraphML export is one connected Sangam component with 102,241 nodes and 111,352 edges. All nine stations, all 36 located OSM parking representatives and all 25 sector representatives are reachable. This confirms point-to-point graph connectivity, not that every point in a sector is walkable. The complete source graph has 63 components; other components are preserved in detached-candidate exports instead of inventing connecting streets.

The 28 main road traces and 41 observed shoreline/approach traces are joined to ground-level OSM roads. Temporary road portions inside the water mask are removed. Endpoint snapping stays within 30 m; ground access links do not cross the water mask above the 0.1 m numerical tolerance. No extra river crossing is invented to make a connectivity test pass. Access edges are low-confidence straight-line interpretations; connectors over 100 m are flagged. Their geometry does not establish a public pedestrian entrance or unobstructed path.

All 27 observed pontoon candidates have both approaches attached. Pontoons 01–04 (west) and 06 (east) land on the upper sandbar; their approaches are low-confidence traces over dry sand and camp lanes to the nearest mela road (pontoon 03 first runs to the pontoon 04 landing, because a direct line crosses the water mask). Treat them as plausible, not verified, through-routes. Slots 28–30 have null geometry. Corrected short bridge endpoints were extended only where the January 27 alignment visibly continued to dry land.

The main serialized graph was independently checked for connectivity, endpoint references, positive lengths and route length sums. All nine station routes are contiguous Dijkstra shortest paths. Jhusi and Chheoki routes use observed pontoon candidates after the approach fixes. Access and bridge availability remain research assumptions.

| Station | Route to Sangam (km) | Nearest mapped rail line (m) |
| --- | ---: | ---: |
| Prayagraj Sangam | 2.358 | 38.14 |
| Jhusi (Jhunsi) | 4.558 | 7.54 |
| Prayagraj Rambagh (Allahabad City) | 4.690 | 0.00 |
| Prayag Junction | 6.364 | 20.83 |
| Prayagraj Junction | 7.227 | 9.90 |
| Chheoki Junction | 9.306 | 22.81 |
| Naini Junction | 9.403 | 15.57 |
| Subedarganj | 10.694 | 14.01 |
| Phaphamau Junction | 12.572 | 6.02 |

OSM station points lie within 0–38.14 m of mapped railways, consistent with points in station/platform footprints. They are not forcibly moved onto a track. These distances test railway proximity; they are not old-TOI position errors.

## Comparison and visual verification

A geographic overlay of the old TOI coordinates would require assigning a transform to an unregistered newspaper drawing, which the task prohibits. Median sector shifts and station errors in metres are therefore undefined and are stored as null. The Original control opens the unwarped local-only reference separately for numbering/adjacency inspection; it does not imply geographic alignment.

Browser screenshots qa/sangam-nose.png and qa/jhusi-side.png were inspected. At Sangam the destination is on the dry bank near the observed tip, and the water mask follows the coarse shoreline. At Jhusi the candidate sectors follow visible tent blocks, with boundaries visibly provisional. The October baseline shows the pre-mela landscape. A 10 m RGB image cannot resolve pedestrian widths, gates, small facilities or bridge operating rules.

Browser checks passed for search, satellite date switching, low-confidence filtering, station route distance display, network/route layers, a zero people count saved across reload, and importing the empty QA workspace afterward. The current source view reports coverage and area limits. Unit tests pass for all legacy IDs, schema migration, valid/invalid imports, coordinate bounds and removal of the TOI assets from dist. The final graph ZIP contains only geodata/audits, with no newspaper images or operational workspace records.

## Remaining evidence needed

Official sector boundaries/IDs and full event extent; verified matches for unresolved legacy references; the three missing bridge locations; field-checked approaches for pontoons 01–04 and 06; actual walking entrances, measured widths (current ones are estimates), obstacles and access restrictions; official temporary mela police locations. A connected centerline graph is supplied for research, but it is not yet a validated JuPedSim walkable domain or live crowd-management model.
