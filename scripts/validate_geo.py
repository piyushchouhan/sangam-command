#!/usr/bin/env python3
"""Independent geometry checks in metric UTM 44N; never compare unregistered pixels to metres."""
import json,pathlib,itertools
from shapely.geometry import shape
from shapely.ops import transform,unary_union
from pyproj import Transformer
R=pathlib.Path(__file__).resolve().parents[1];D=R/'data';T=Transformer.from_crs(4326,32644,always_xy=True).transform
load=lambda p:json.loads((D/p).read_text())
metric=lambda f:transform(T,shape(f['geometry']))
sectors=load('mela/sectors.geojson')['features'];gs=[metric(f).buffer(0)for f in sectors]
assert all(shape(f['geometry']).is_valid for f in sectors)
water=unary_union([metric(f)for f in load('mela/river_banks.geojson')['features']])
assert len(gs)==25 and all(g.is_valid and not g.is_empty for g in gs)
overlap=sum(a.intersection(b).area for a,b in itertools.combinations(gs,2));wet=sum(g.intersection(water).area for g in gs)
assert overlap<.01 and wet<.01,(overlap,wet)
tracks=unary_union([metric(f)for f in load('osm/railways.geojson')['features'] if f['geometry'] and f['geometry']['type'] in ('LineString','MultiLineString')])
stations=load('osm/stations_normalized.geojson')['features'];station_checks=[{'id':f['properties']['id'],'nearest_railway_m':round(metric(f).distance(tracks),2)}for f in stations]
assert len(stations)==9 and all(f['nearest_railway_m']<100 for f in station_checks),station_checks
for f in load('mela/mela_roads.geojson')['features']:assert metric(f).intersection(water).length<.1
report={'sector_area_ha':round(sum(g.area for g in gs)/10000,3),'reported_event_area_ha':4000,'event_extent_complete':False,'sector_overlap_m2':round(overlap,6),'sector_water_overlap_m2':round(wet,6),'station_railway_checks':station_checks,'station_old_image_position_error_m':None,'old_new_sector_shift_m':None,'comparison_limitation':'Old newspaper geometry has no geographic transform; numerical displacement would require the prohibited image registration.'}
(D/'geometry-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
