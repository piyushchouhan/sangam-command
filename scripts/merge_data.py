#!/usr/bin/env python3
"""Merge source GeoJSON into app index; retain unmatched IDs without invented positions."""
import json,pathlib,shutil
from shapely.geometry import shape,mapping,Polygon
from shapely.ops import transform
from pyproj import Transformer
R=pathlib.Path(__file__).resolve().parents[1];D=R/'data';OUT=R/'dist';B=Transformer.from_crs(4326,32644,always_xy=True).transform
legacy=json.loads((D/'mela/reference_inventory.json').read_text());old={f['id']:f for f in legacy['features']};features={}
def load(p):return json.loads((D/p).read_text())
def add(f,typ=None):
 p=dict(f['properties']);p['id']=f.get('id',p.get('id'));p['type']=typ or p.get('type','other');p['geometry']=f['geometry'];p.setdefault('name',p['id']);p.setdefault('description',p.get('method','OpenStreetMap geometry, snapshot date shown in provenance.' if p.get('source')=='osm' else 'Observed physical geometry from georeferenced Sentinel-2 imagery; approximate at 10 m resolution.'))
 if f['geometry']:
  g=shape(f['geometry']);rep=g.representative_point() if g.geom_type in ['Polygon','MultiPolygon'] else g.centroid;p['coordinates']=p.get('label_coordinates',[rep.x,rep.y])
  if g.geom_type in ['Polygon','MultiPolygon']:p['area_ha']=round(transform(B,g).area/10000,3)
 else:p['coordinates']=None;p['location_status']='unresolved'
 features[p['id']]=p
for path,typ in [('mela/sectors.geojson','sector'),('osm/stations_normalized.geojson','station'),('osm/temples_matched.geojson','landmark'),('mela/landmarks_google.geojson','landmark'),('osm/police_normalized.geojson','police'),('mela/parking.geojson','parking_area'),('mela/pontoon_bridges.geojson','crossing'),('mela/river_banks.geojson','water')]:
 for f in load(path)['features']:add(f,typ)
# Canonical Sangam source ID remains stable, independent of its original image position.
nose=load('mela/sangam_nose.geojson')['features'][0];p=nose['properties'];p['id']='sangam';nose['id']='sangam';add(nose,'water')
for id,f in old.items():
 if id in features:continue
 p={k:v for k,v in f.items() if k not in ['xy','polygon','line','confidence','source']};p.update(source='toi_reference',confidence='low',geometry=None,coordinates=None,location_status='unresolved',description='Legacy reference retained for saved records. No independently verified geographic correspondence is available. Not drawn on the geographic map.');features[id]=p
# Source geometries retain complete metadata in standalone files; map index includes manageable POIs.
fc={'schemaVersion':2,'title':'Sangam Command geographic research atlas','coordinateSystem':{'crs':'EPSG:4326','order':'longitude,latitude','units':'degrees','georeferenced':True},'source':{'title':'OSM and Copernicus Sentinel-2','mapYear':2025,'note':'Physical geometry from OSM and 2025-01-27 Sentinel imagery; sector numbering/order from TOI. Sector assignments provisional. Unresolved references have null geometry.'},'statistics':legacy['statistics'],'features':list(features.values()),'basemap':{'url':'https://tile.openstreetmap.org/{z}/{x}/{y}.png','attribution':'© OpenStreetMap contributors (ODbL)'},'datasets':{'sentinel':'data/sentinel2/manifest.json','roads':'data/osm/roads.geojson','bridges':'data/osm/bridges.geojson','railways':'data/osm/railways.geojson','melaRoads':'data/mela/mela_roads.geojson','pontoonApproaches':'data/mela/pontoon_approaches.geojson','temporaryPolice':'data/mela/police_temporary.geojson','network':'data/network/render_edges.geojson','routes':'data/network/routes.geojson','validation':'data/network/validation.json'}}
(OUT/'map-data.json').write_text(json.dumps(fc,ensure_ascii=False,indent=2))
for folder in ['osm','mela','network']:
 target=OUT/'data'/folder;target.mkdir(parents=True,exist_ok=True)
 for p in (D/folder).glob('*'):
  if p.name in ['overpass.json','edges.geojson','nodes.geojson','graph.graphml','disconnected_nodes.geojson','disconnected_edges.geojson']:continue
  if p.suffix in ['.geojson','.json']:shutil.copy2(p,target/p.name)
target=OUT/'data/sentinel2';target.mkdir(parents=True,exist_ok=True);shutil.copy2(D/'sentinel2/manifest.json',target/'manifest.json')
print('Features',len(features),'mapped',sum(bool(f['geometry'])for f in features.values()),'unresolved',sum(not f['geometry']for f in features.values()))
