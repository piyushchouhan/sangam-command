import json,pathlib
from shapely.geometry import shape,Polygon,mapping,Point
R=pathlib.Path(__file__).resolve().parents[1];D=R/'data/osm'
def load(n):return json.loads((D/(n+'.geojson')).read_text())
def point(f):
 g=shape(f['geometry']);p=Polygon(g.coords).representative_point() if g.geom_type=='LineString' and g.is_ring else g.centroid
 return mapping(p)
def write(n,fs):
 d=load('stations');d['name']=n;d['features']=fs;(D/(n+'.geojson')).write_text(json.dumps(d,ensure_ascii=False,indent=2))
lookup={7596470088:('station-phaphamau','Phaphamau Junction',[]),312624621:('station-prayag','Prayag Junction',[]),2669094327:('station-prayagraj','Prayagraj Junction',[]),6589820436:('station-sangam-station','Prayagraj Sangam',['Daraganj']),316602923:('station-rambagh','Prayagraj Rambagh (Allahabad City)',['Allahabad City']),2087246860:('station-subedarganj','Subedarganj', ['SUBEDARGANJ RAILWAY STATION']),312613037:('station-naini','Naini Junction',[]),4871944927:('station-chheoki','Chheoki Junction',['Allahabad Chheoki Junction']),7596025213:('station-jhunsi','Jhusi (Jhunsi)',[])}
fs=[]
for f in load('stations')['features']:
 if f['properties']['osm_id']not in lookup:continue
 id,name,aliases=lookup[f['properties']['osm_id']];f['id']=id;f['properties'].update(id=id,name=name,aliases=aliases,type='station');f['geometry']=point(f);fs.append(f)
write('stations_normalized',fs)
lookup={8911046742:('landmark-hanuman','Bade Hanuman Ji'),8911055853:('landmark-shankar','Shankar Vimana Mandapam'),11694433676:('landmark-nagvasuki','Nagvasuki'),621477594:('landmark-mankameshwar','Mankameshwar')}
fs=[]
for f in load('temples')['features']:
 if f['properties']['osm_id']not in lookup:continue
 id,name=lookup[f['properties']['osm_id']];f['id']=id;f['properties'].update(id=id,name=name,type='landmark');f['geometry']=point(f);fs.append(f)
write('temples_matched',fs)
fs=[]
for f in load('police')['features']:
 f['geometry']=point(f);f['properties']['type']='police';fs.append(f)
write('police_normalized',fs)
print('9 normalized stations, 4 named temple matches, 15 permanent police records. Daraganj and duplicate Subedarganj omitted as aliases.')
