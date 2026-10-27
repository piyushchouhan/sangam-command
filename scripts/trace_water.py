#!/usr/bin/env python3
"""Conservative RGB channel extraction from January 27 Sentinel-2.
This is not NDWI: the inputs only contain rendered R,G,B. A manually
inspected river corridor limits tree/shadow contamination. Connected water
pixels are vectorized in their native affine/CRS; no TOI coordinates used.
"""
import argparse,json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import shapes,geometry_mask
from scipy.ndimage import binary_closing,label,binary_fill_holes
from skimage.morphology import remove_small_holes
from shapely.geometry import shape,mapping,Polygon,Point
from shapely.ops import unary_union,transform
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[1]
SRC=Path('/Users/piyushchauhan/personal-projects/crowd-research/data/sentinel2/prayagraj_sangam_2025-01-27.tif')
# Loose river corridor, digitized in this georeferenced image, not TOI.
CORRIDOR=[(819,0),(852,0),(845,85),(819,152),(774,203),(728,253),(701,319),(692,368),(714,417),(715,478),(712,541),(750,597),(800,636),(839,698),(877,778),(917,852),(996,951),(936,951),(865,866),(810,785),(766,712),(724,664),(671,621),(635,597),(566,581),(497,571),(432,574),(351,588),(262,607),(174,642),(95,676),(0,741),(0,647),(80,617),(164,584),(246,551),(315,530),(392,504),(465,496),(522,507),(581,526),(635,532),(680,556),(667,518),(658,466),(658,410),(648,377),(650,327),(654,284),(658,240),(652,219),(678,195),(700,181),(712,150),(741,123),(767,109),(782,80),(802,65),(817,36)]
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=SRC);a=p.parse_args()
 extended=ROOT/'data/sentinel2/reference-extended-2025-01-27.tif'
 if a.input==SRC and extended.exists():a.input=extended
 with rasterio.open(a.input) as ds:
  rgb=ds.read().astype(float);r,g,b=rgb
  offset=round((ds.transform.f-2817890)/10)
  corridor=Polygon([ds.transform*(x,y+offset) for x,y in CORRIDOR])
  if offset==600:
   north=[(0,113),(90,127),(143,166),(160,205),(240,250),(300,250),(350,267),(420,247),(500,242),(558,240),(585,248),(610,278),(675,312),(710,343),(738,360),(779,363),(795,415),(812,467),(844,517),(850,566),(852,605),(815,605),(773,578),(742,565),(725,539),(697,500),(686,465),(690,434),(677,399),(650,393),(621,357),(592,349),(554,327),(530,300),(499,285),(458,284),(412,288),(361,303),(300,300),(268,288),(228,300),(197,303),(164,280),(142,264),(131,236),(125,207),(109,177),(80,162),(42,151),(20,152),(0,170)]
   corridor=unary_union([corridor,Polygon([ds.transform*(x,y) for x,y in north])])
  inside=geometry_mask([mapping(corridor)],out_shape=(ds.height,ds.width),transform=ds.transform,invert=True)
  mask=(r<125)&(g<145)&(b<120)&(g-r>2)&(g-b>2)&inside
  mask=binary_closing(mask,iterations=1)&inside
  lab,n=label(mask);counts=np.bincount(lab.ravel());counts[0]=0
  keep=[i for i,c in enumerate(counts) if c>=50];mask=np.isin(lab,keep)
  mask=remove_small_holes(mask,area_threshold=20)&inside
  polys=[shape(geo) for geo,v in shapes(mask.astype('uint8'),mask=mask,transform=ds.transform) if v]
  geom=unary_union(polys).buffer(0).simplify(7,preserve_topology=True)
  t=Transformer.from_crs(ds.crs,4326,always_xy=True).transform
  out=ROOT/'data/mela';out.mkdir(parents=True,exist_ok=True)
  prop={'id':'river-main','name':'Ganga–Yamuna channels, 27 January 2025','kind':'river','source':'traced:sentinel2-2025-01-27','confidence':'medium','area_ha':round(geom.area/10000,3),'method':'RGB green-dark connected-channel classification, manually constrained river corridor; 10 m imagery; banks approximate ±20 m.','reference_date':'2025-01-27','sentinel_scene':'S2B_44RNP_20250127_0_L2A'}
  (out/'river_banks.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[{'type':'Feature','id':'river-main','properties':prop,'geometry':mapping(transform(t,geom))}]},indent=2))
  # Last dry sand at western confluence tip. Native pixel-centre coordinates.
  tip=Point(ds.transform*(669,543+offset));xy=t(tip.x,tip.y)
  nose={'type':'Feature','id':'landmark-sangam','properties':{'id':'landmark-sangam','name':'Sangam nose','kind':'landmark','source':'traced:sentinel2-2025-01-27','confidence':'medium','position_uncertainty_m':20,'note':'Dry-land tip of the west confluence bank observed 2025-01-27; not centre of water confluence.'},'geometry':{'type':'Point','coordinates':xy}}
  (out/'sangam_nose.geojson').write_text(json.dumps({'type':'FeatureCollection','features':[nose]},indent=2))
  from PIL import Image,ImageDraw
  im=Image.fromarray(rgb.transpose(1,2,0).astype('uint8')).convert('RGBA');overlay=np.zeros((ds.height,ds.width,4),dtype='uint8');overlay[mask]=[20,150,255,110];im=Image.alpha_composite(im,Image.fromarray(overlay));d=ImageDraw.Draw(im);d.ellipse((664,538+offset,674,548+offset),outline='red',width=2);im.save('/private/tmp/sangam-water-check.png')
  print({'area_ha':prop['area_ha'],'sangam_nose_lonlat':xy,'polygons':len(polys)})
if __name__=='__main__':main()
