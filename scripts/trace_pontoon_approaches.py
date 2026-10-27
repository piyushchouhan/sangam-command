#!/usr/bin/env python3
"""Trace January 27 visible bank lanes and temporary bridge approaches.
All pixel vertices refer to the ORIGINAL georeferenced Sentinel crop, whose
UTM affine is (582420,10,0,2817890,0,-10), not a newspaper graphic.
These are manually inspected road alignments, not shortest-line connectors.
Width/access control cannot be established by 10 m RGB. Upper island paths
remain unresolved. Ground traces crossing the water mask are reported and
not exported; neither the water mask nor 30 m graph snap threshold is changed.
"""
import json
from pathlib import Path
from pyproj import Transformer
from shapely.geometry import LineString,shape,mapping
from shapely.ops import transform,unary_union
ROOT=Path(__file__).resolve().parents[1]
PROJECT=Transformer.from_crs(4326,32644,always_xy=True).transform
UNPROJECT=Transformer.from_crs(32644,4326,always_xy=True).transform
TRACES=[
 ('West bank margin lane', 'medium',[(650,430),(658,430),(658,438),(658,446),(659,454),(660,462),(661,470),(662,479),(664,489),(665,499),(668,509),(669,518),(672,532),(666,535)]),
 ('Jhusi bank margin lane','medium',[(710,450),(711,460),(710,469),(708,477),(708,485),(708,492),(709,504),(712,513),(713,519),(714,532)]),
 ('Jhusi upstream bank lane','medium',[(699,326),(699,331),(697,340),(694,350),(692,356),(691,365),(693,375),(695,387),(698,400),(700,408),(715,414)]),
 ('Pontoon 07 eastern approach','medium',[(715,264),(714,270),(710,281),(706,282)]),
 ('Pontoon 09 eastern approach','medium',[(696,331),(699,331)]),
 ('Pontoon 10 eastern approach','medium',[(689,355),(692,356)]),
 ('Pontoon 11 western approach','medium',[(651,374),(647,371)]),
 ('Pontoon 11 eastern approach','medium',[(691,387),(695,387)]),
 ('Pontoon 12 western approach','medium',[(665,438),(658,438)]),
 ('Pontoon 13 western approach','medium',[(665,446),(658,446)]),
 ('Pontoon 14 western approach','medium',[(666,454),(659,454)]),
 ('Pontoon 15 western approach','medium',[(666,462),(660,462)]),
 ('Pontoon 16 western approach','medium',[(667,470),(661,470)]),
 ('Pontoon 17 western approach','medium',[(668,479),(662,479)]),
 ('Pontoon 18 western approach','medium',[(669,489),(664,489)]),
 ('Pontoon 19 western approach','medium',[(670,499),(665,499)]),
 ('Pontoon 20 western approach','medium',[(671,509),(668,509)]),
 ('Pontoon 21 western approach','medium',[(672,518),(669,518)]),
 ('Pontoon 13 eastern approach','medium',[(708,460),(711,460)]),
 ('Pontoon 14 eastern approach','medium',[(707,469),(710,469)]),
 ('Pontoon 15 eastern approach','medium',[(706,477),(708,477)]),
 ('Pontoon 16 eastern approach','medium',[(705,485),(708,485)]),
 ('Pontoon 17 eastern approach','medium',[(705,492),(708,492)]),
 ('Pontoon 18 eastern approach','medium',[(706,504),(709,504)]),
 ('Pontoon 19 eastern approach','medium',[(708,513),(712,513)]),
 ('Pontoon 20 eastern approach','medium',[(710,523),(713,523),(713,519)]),
 ('Pontoon 21 eastern approach','medium',[(711,532),(714,532)]),
 ('Pontoon 22 Arail approach','medium',[(728,680),(715,692),(704,702),(702,687)]),
 ('Pontoon 22 Jhusi approach','medium',[(792,613),(802,604),(813,600)]),
 ('Pontoon 23 Arail approach','low',[(765,730),(757,734),(745,743)]),
 ('Pontoon 24 Arail approach','low',[(789,758),(775,766),(761,779)]),
 ('Pontoon 25 Arail approach','medium',[(824,805),(805,817),(790,827),(783,838)]),
 ('Pontoon 26 Arail approach','medium',[(867,854),(854,863),(839,872)]),
 ('Pontoon 26 eastern approach','low',[(929,822),(924,825)]),
 ('Pontoon 01 Jhusi continuation','medium',[(844,34),(859,39),(876,45),(885,47)]),
 ('Pontoon 02 Jhusi continuation','medium',[(834,100),(847,104),(869,115)]),
 ('Pontoon 03 Jhusi continuation','medium',[(815,149),(824,156),(850,167)]),
 ('Pontoon 04 Jhusi continuation','medium',[(811,156),(822,164),(848,175)]),
 ('Pontoon 05 Jhusi continuation','medium',[(774,199),(800,209),(829,218)]),
 ('Pontoon 27 western approach lane','medium',[(718,-116),(690,-114),(662,-112),(630,-111),(605,-110)]),
 ('Pontoon 27 Jhusi continuation','medium',[(820,-122),(832,-122),(850,-119),(865,-116)]),
 # Upper sandbar landings: dry sand and camp lanes run from each landing to the nearest mela road.
 ('Pontoon 01 sandbar approach','low',[(817,22),(785,19),(750,17)]),
 ('Pontoon 02 sandbar approach','low',[(797,80),(775,85),(755,90)]),
 ('Pontoon 03 sandbar approach','low',[(766,134),(762,140),(741,155),(724,166),(710,173)]),
 ('Pontoon 04 sandbar approach','low',[(762,140),(741,155),(724,166),(710,173)]),
 ('Pontoon 06 sand tongue approach','low',[(676,232),(687,213),(700,193),(710,173)])
]
SANDBAR={'Pontoon 01 sandbar approach':('pontoon-01','west'),'Pontoon 02 sandbar approach':('pontoon-02','west'),'Pontoon 03 sandbar approach':('pontoon-03','west'),'Pontoon 04 sandbar approach':('pontoon-04','west'),'Pontoon 06 sand tongue approach':('pontoon-06','east')}
def main():
 water=unary_union([transform(PROJECT,shape(f['geometry'])) for f in json.loads((ROOT/'data/mela/river_banks.geojson').read_text())['features'] if f.get('geometry')])
 fs=[];rejected=[]
 for i,(name,confidence,pixels) in enumerate(TRACES,1):
  ident=f'pontoon-approach-{i:03d}';utm=LineString([(582420+x*10,2817890-y*10) for x,y in pixels]);wet=utm.intersection(water).length
  if wet>.1:
   rejected.append({'id':ident,'name':name,'reason':'visible_approach_disagrees_with_water_mask','water_intersection_m':round(wet,3)});continue
  props={'id':ident,'name':name,'kind':'mela_road','source':'traced:sentinel2-2025-01-27','confidence':confidence,'approx_width_m':5.5,'width_source':'google_maps_measured','width_confidence':'low','length_m':round(utm.length,3),'water_intersection_m':round(wet,3),'reference_date':'2025-01-27','note':'Manually traced visible bank or camp approach. 10 m RGB does not establish legal access or bridge opening status.'}
  fs.append({'type':'Feature','id':ident,'properties':props,'geometry':mapping(transform(UNPROJECT,utm))})
 result={'type':'FeatureCollection','name':'Visible pontoon approach roads','source_image':'prayagraj_sangam_2025-01-27.tif','rejected_traces':rejected,'unresolved_approaches':[{'pontoon_id':SANDBAR[r['name']][0],'endpoint':SANDBAR[r['name']][1],'reason':'Sandbar approach trace crosses the water mask; no continuous ground path established at 10 m RGB resolution.'} for r in rejected if r['name'] in SANDBAR],'features':fs}
 (ROOT/'data/mela/pontoon_approaches.geojson').write_text(json.dumps(result,indent=2));print(json.dumps({'exported':len(fs),'rejected':rejected},indent=2))
if __name__=='__main__':main()
