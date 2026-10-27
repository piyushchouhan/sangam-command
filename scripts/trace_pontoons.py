#!/usr/bin/env python3
"""Export visually inspected January 27 bridge alignments from native raster.
Pixels below are Sentinel-2 pixel coordinates, never TOI graphic coordinates.
A line crossing water is interpreted as a temporary crossing at 10 m GSD;
construction type, opening status, load/width are not established by RGB.
Legacy schematic crossing IDs require human correspondence verification.
"""
import argparse,json
from pathlib import Path
import rasterio
from pyproj import Transformer
from shapely.geometry import LineString,mapping
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/Users/piyushchauhan/personal-projects/crowd-research/data/sentinel2/prayagraj_sangam_2025-01-27.tif')
# Sorted north-to-south within January 27 coverage; independent observation IDs.
TRACES=[
 [(817,22),(844,34)],
 [(797,80),(834,100)],
 [(766,134),(815,149)],
 [(762,140),(811,156)],
 [(710,173),(774,199)],
 [(654,214),(676,232)],
 [(662,260),(715,264)],
 [(658,320),(697,326)],
 [(658,325),(696,331)],
 [(655,343),(689,355)],
 [(651,374),(691,387)],
 # Permanent rail/highway bridge pair near y=391 and y=415 omitted.
 [(665,438),(709,454)],
 [(665,446),(708,460)],
 [(666,454),(707,469)],
 [(666,462),(706,477)],
 [(667,470),(705,485)],
 [(668,479),(705,492)],
 [(669,489),(706,504)],
 [(670,499),(708,513)],
 [(671,509),(710,523)],
 [(672,518),(711,532)],
 [(728,680),(792,613)],
 [(765,730),(849,681)],
 [(789,758),(876,725)],
 [(824,805),(897,775)],
 [(867,854),(929,822)],
]
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=SRC);a=p.parse_args()
 features=[]
 extended=ROOT/'data/sentinel2/reference-extended-2025-01-27.tif'
 if a.input==SRC and extended.exists():a.input=extended
 with rasterio.open(a.input) as ds:
  t=Transformer.from_crs(ds.crs,4326,always_xy=True)
  im=Image.fromarray(ds.read().transpose(1,2,0)).convert('RGB');draw=ImageDraw.Draw(im)
  offset=round((ds.transform.f-2817890)/10)
  traces=[[(x,y+offset) for x,y in line] for line in TRACES]
  if offset==600:traces.append([(718,484),(820,478)])
  for i,pixels in enumerate(traces,1):
   utm=[ds.transform*xy for xy in pixels];ll=[t.transform(*xy) for xy in utm];ident=f'pontoon-{i:02d}'
   props={'id':ident,'name':f'Observed temporary crossing {i:02d}','kind':'pontoon','source':'traced:sentinel2-2025-01-27','confidence':'medium','length_m':round(LineString(utm).length,2),'approx_width_m':5.0,'width_source':'estimate','width_confidence':'low','reference_date':'2025-01-27','sentinel_scene':'S2B_44RNP_20250127_0_L2A','position_uncertainty_m':20,'note':'Visible linear crossing interpreted from 10 m RGB. Official bridge name, type and operational status unverified. This is an observation ID, not the official bridge number.'}
   features.append({'type':'Feature','id':ident,'properties':props,'geometry':{'type':'LineString','coordinates':ll}})
   draw.line(pixels,fill=(255,60,220),width=2);draw.text((pixels[-1][0]+3,pixels[-1][1]),str(i),fill=(255,0,0))
  for i in range(len(traces)+1,31):
   ident=f'pontoon-{i:02d}';features.append({'type':'Feature','id':ident,'properties':{'id':ident,'name':f'Unresolved temporary bridge inventory slot {i:02d}','kind':'pontoon','source':'toi_reference','confidence':'low','length_m':None,'approx_width_m':None,'note':'User-supplied inventory total is 30. No location asserted: not confidently distinguishable within supplied imagery. Excluded from routing.'},'geometry':None})
  im.save('/private/tmp/sangam-pontoon-check.png')
 out={'type':'FeatureCollection','inventory_target':30,'observed_count':len(traces),'unresolved_count':30-len(traces),'legacy_ids_note':'crossing-01…13 remain separate unresolved TOI references unless their identity can be verified; no rank-based automatic reassignment.','features':features}
 (ROOT/'data/mela/pontoon_bridges.geojson').write_text(json.dumps(out,indent=2));print({'observed':len(traces),'unresolved':30-len(traces)})
if __name__=='__main__':main()
