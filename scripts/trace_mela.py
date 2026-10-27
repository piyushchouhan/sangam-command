#!/usr/bin/env python3
"""Provisional physical camp extents from inspected Jan27 RGB, NOT newspaper geometry.
Pixel vertices below refer only to the georeferenced Sentinel grid (original crop origin).
Sector labels/order use the newspaper as a topology reference; boundaries are research hypotheses.
"""
import json,pathlib
import rasterio
from pyproj import Transformer
from shapely.geometry import Polygon,LineString,Point,shape,mapping
from shapely.ops import transform,unary_union
R=pathlib.Path(__file__).resolve().parents[1];D=R/'data/mela';D.mkdir(exist_ok=True,parents=True)
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--input',type=pathlib.Path,default=pathlib.Path('/Users/piyushchauhan/personal-projects/crowd-research/data/sentinel2/prayagraj_sangam_2025-01-27.tif'));args=parser.parse_args()
with rasterio.open(args.input)as ds:A=ds.transform
F=Transformer.from_crs(32644,4326,always_xy=True).transform;B=Transformer.from_crs(4326,32644,always_xy=True).transform
P={
9:[(495,-300),(541,-285),(570,-245),(566,-228),(538,-257),(510,-272)],
8:[(566,-228),(570,-245),(598,-230),(643,-218),(692,-183),(701,-128),(698,-67),(730,-38),(744,-16),(610,-22),(580,-95)],
7:[(610,-22),(744,-16),(778,13),(799,35),(800,69),(753,90),(592,70)],
6:[(592,70),(753,90),(800,69),(794,111),(752,151),(704,190),(658,219),(615,195),(553,164)],
4:[(648,220),(665,230),(663,280),(662,325),(656,375),(664,416),(664,449),(646,445),(645,402),(639,369),(640,320),(640,270)],
1:[(407,389),(453,379),(500,381),(541,391),(543,432),(500,436),(448,424),(421,428)],
2:[(541,391),(580,383),(621,390),(646,402),(646,445),(604,446),(570,430),(543,432)],
3:[(604,446),(646,445),(664,449),(665,487),(677,533),(670,545),(637,529),(598,523),(590,484)],
5:[(700,346),(732,350),(726,384),(715,414),(695,407),(681,383)],
10:[(786,-220),(852,-204),(925,-171),(951,-131),(909,-101),(839,-105),(821,-145)],
11:[(839,-105),(909,-101),(951,-131),(982,-82),(977,-24),(960,25),(844,5),(849,-34)],
12:[(844,5),(960,25),(944,81),(815,64)],
13:[(815,64),(944,81),(928,127),(801,114)],
14:[(801,114),(928,127),(910,189),(773,176)],
15:[(773,176),(910,189),(892,247),(738,229)],
16:[(738,229),(892,247),(874,300),(706,282)],
17:[(706,282),(874,300),(856,356),(732,350),(700,346),(697,322)],
18:[(732,350),(856,356),(840,410),(715,414),(726,384)],
19:[(695,407),(715,414),(840,410),(823,465),(703,455)],
20:[(703,455),(823,465),(809,524),(711,519)],
22:[(711,519),(777,523),(780,570),(795,613),(754,590),(721,553)],
21:[(777,523),(809,524),(805,562),(831,606),(816,626),(795,613),(780,570)],
23:[(273,603),(351,583),(431,572),(499,570),(564,578),(619,596),(611,612),(550,594),(485,588),(416,590),(355,602),(280,619)],
24:[(619,596),(648,610),(678,641),(703,669),(735,721),(762,765),(798,811),(777,826),(744,780),(709,730),(682,686),(657,662),(631,631),(611,612)],
25:[(798,811),(827,836),(856,870),(901,917),(929,950),(872,950),(832,899),(807,865),(777,826)]}
water=unary_union([transform(B,shape(f['geometry'])) for f in json.load(open(D/'river_banks.geojson'))['features']])
features=[];used=Polygon()
for n in range(1,26):
 p=Polygon([A*xy for xy in P[n]]).buffer(0).difference(water.buffer(5)).difference(used).buffer(0)
 if p.is_empty:raise ValueError(n)
 used=unary_union([used,p]);rep=p.representative_point();id=f'sector-{n:02}'
 features.append({'type':'Feature','id':id,'geometry':mapping(transform(F,p)),'properties':{'id':id,'name':f'Sector {n}','type':'sector','number':n,'zone':'City bank' if n<=4 or 6<=n<=9 else 'Arail bank' if n>=23 else 'Jhunsi bank','source':'traced:sentinel2-2025-01-27','confidence':'low','area_ha':round(p.area/10000,3),'label_coordinates':list(F(rep.x,rep.y)),'method':'Physical perimeter digitized against Sentinel tent blocks/roads; river mask and prior sector overlap removed. Administrative assignment is provisional; TOI used only for sector numbering and relative order.','numbering_source':'toi_reference','boundary_status':'research_hypothesis','description':'Satellite-positioned camp extent with provisional sector assignment. Not an official administrative boundary.'}})
(D/'sectors.geojson').write_text(json.dumps({'type':'FeatureCollection','features':features},indent=2))
# Roads inspected in the satellite, not inferred from the newspaper graphic.
roads=[
[(560,-258),(587,-180),(610,-95),(630,-15),(621,65),(602,137),(626,192)],
[(600,-175),(657,-184),(690,-161)],[(610,-95),(663,-98),(702,-89)],[(630,-15),(702,-3),(750,17)],[(621,65),(686,75),(755,91)],[(602,137),(669,158),(715,174)],
[(840,-171),(866,-117),(882,-61),(892,0),(878,70),(863,135),(838,207),(820,269),(801,335),(784,400),(769,467),(775,526),(799,586)],
[(928,-151),(951,-89),(943,-15),(925,51),(906,122),(883,190),(862,260),(841,325),(822,391),(805,458),(797,523)],
[(838,-106),(909,-101),(951,-131)],[(844,5),(960,25)],[(815,64),(944,81)],[(801,114),(928,127)],[(773,176),(910,189)],[(738,229),(892,247)],[(706,282),(874,300)],[(700,346),(732,350),(856,356)],[(695,407),(715,414),(840,410)],[(703,455),(823,465)],[(711,519),(809,524)],
[(647,226),(650,266),(650,326),(647,371),(650,410),(648,450),(650,488),(666,535),(670,544)],
[(421,409),(477,411),(539,414),(583,411),(626,414),(650,410)],
[(598,446),(620,465),(646,484),(650,488)],[(610,520),(638,525),(666,535)],
[(280,610),(355,592),(429,582),(492,580),(560,587),(616,604),(648,624),(678,654),(702,687),(735,738),(765,782),(798,828),(835,871),(880,926),(896,947)],
[(606,635),(616,604)],[(703,698),(702,687)],[(783,838),(798,828)],[(857,941),(880,926)],
]
fs=[]
for i,coords in enumerate(roads,1):
 line=LineString([A*xy for xy in coords]).difference(water.buffer(2));fs.append({'type':'Feature','id':f'mela-road-{i:03}','geometry':mapping(transform(F,line)),'properties':{'id':f'mela-road-{i:03}','name':f'Mela road trace {i:03}','type':'road','kind':'mela_road','source':'traced:sentinel2-2025-01-27','confidence':'medium','length_m':round(line.length,2),'approx_width_m':5.5,'width_source':'google_maps_measured','width_confidence':'medium','method':'Visual digitization of main light linear routes in 10 m RGB image; water-mask portions removed; route centreline approximate. Width: chequered-plate mela roads measured on Google Maps satellite (Kila Ghat Rd 5.4 m, Sangam Marg ~5 m, Annapurna Rd ~5.5 m).'}})
(D/'mela_roads.geojson').write_text(json.dumps({'type':'FeatureCollection','features':fs},indent=2))
# OSM parking geometries supply actual locations; no arbitrary mapping from old colour blobs.
parking=[]
for f in json.load(open(R/'data/osm/parking.geojson'))['features']:
 g=shape(f['geometry']);g=Polygon(g.coords).buffer(0) if g.geom_type=='LineString' and g.is_ring else g
 f['geometry']=mapping(g);f['properties'].update(type='parking_area',parkingClass='osm_mapped',area_ha=round(transform(B,g).area/10000,3) if g.geom_type in ['Polygon','MultiPolygon'] else None);parking.append(f)
(D/'parking.geojson').write_text(json.dumps({'type':'FeatureCollection','features':parking},indent=2))
(D/'police_temporary.geojson').write_text(json.dumps({'type':'FeatureCollection','name':'Police (mela, temporary)','source':'toi_reference','confidence':'low','description':'Awaiting official UP Police / Mela Authority locations.','features':[]},indent=2))
print('25 provisional sectors',round(used.area/10000,2),'ha;',len(fs),'mela roads;',len(parking),'OSM parking records')
