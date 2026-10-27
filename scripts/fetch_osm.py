#!/usr/bin/env python3
"""Fetch OSM source geometry with IDs/tags retained. Use --refresh to refetch."""
import argparse,json,datetime,pathlib,time,requests
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'data/osm';OUT.mkdir(parents=True,exist_ok=True)
BBOX='25.33,81.78,25.53,81.98'
QUERY=f'''[out:json][timeout:180];(nwr[railway~"^(station|halt)$"]({BBOX});nwr[amenity=police]({BBOX});nwr[amenity=place_of_worship]({BBOX});way[highway]({BBOX});way[bridge]({BBOX});way[railway=rail]({BBOX});nwr[amenity=parking]({BBOX});nwr[place]({BBOX}););out body geom;'''
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--refresh',action='store_true');args=ap.parse_args();raw=OUT/'overpass.json'
 if args.refresh or not raw.exists():
  r=requests.post('https://overpass-api.de/api/interpreter',data={'data':QUERY},headers={'User-Agent':'SangamCommandResearch/2.0 (+https://sangam-command-map.piyushnchouhan.chatgpt.site)'},timeout=240);r.raise_for_status();d=r.json();d['fetched_at']=datetime.datetime.now(datetime.timezone.utc).isoformat();raw.write_text(json.dumps(d))
 else:d=json.loads(raw.read_text())
 layers={k:[] for k in ['stations','police','temples','roads','bridges','railways','parking','localities']}
 for e in d['elements']:
  t=e.get('tags',{});geom=None
  if e['type']=='node':geom={'type':'Point','coordinates':[e['lon'],e['lat']]}
  elif e['type']=='way' and e.get('geometry'):
   coords=[[n['lon'],n['lat']] for n in e['geometry'] if 'lon'in n]
   if len(coords)>1:geom={'type':'LineString','coordinates':coords}
  elif e['type']=='relation':
   coords=[[[n['lon'],n['lat']] for n in m.get('geometry',[]) if 'lon'in n] for m in e.get('members',[])];coords=[c for c in coords if len(c)>1]
   if coords:geom={'type':'MultiLineString','coordinates':coords}
  if not geom:continue
  props={'id':f'osm-{e["type"]}-{e["id"]}','name':t.get('name:en',t.get('name',t.get('highway','Unnamed OSM feature'))),'osm_type':e['type'],'osm_id':e['id'],'osm_url':f'https://www.openstreetmap.org/{e["type"]}/{e["id"]}','source':'osm','confidence':'high','fetched_at':d['fetched_at'],'tags':t}
  if 'nodes'in e:props['node_ids']=e['nodes']
  f={'type':'Feature','id':props['id'],'geometry':geom,'properties':props}
  if t.get('railway')in ['station','halt']:layers['stations'].append(f)
  if t.get('amenity')=='police':layers['police'].append(f)
  if t.get('amenity')=='place_of_worship':layers['temples'].append(f)
  if t.get('amenity')=='parking':layers['parking'].append(f)
  if 'place'in t:layers['localities'].append(f)
  if 'highway'in t:
   props['walkable']=t['highway']not in ['motorway','motorway_link','construction','proposed'] and t.get('foot')not in ['no','private'] and (t.get('access')not in ['no','private'] or t.get('foot')in ['yes','designated','permissive']);layers['roads'].append(f)
  if t.get('bridge') not in [None,'no']:layers['bridges'].append(f)
  if t.get('railway')=='rail':layers['railways'].append(f)
 for k,features in layers.items():(OUT/(k+'.geojson')).write_text(json.dumps({'type':'FeatureCollection','name':k,'fetched_at':d['fetched_at'],'licence':'ODbL-1.0','bbox':[81.78,25.33,81.98,25.53],'features':features},ensure_ascii=False))
 print(json.dumps({k:len(v)for k,v in layers.items()}))
if __name__=='__main__':main()
