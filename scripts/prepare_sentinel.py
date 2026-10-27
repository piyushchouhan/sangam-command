#!/usr/bin/env python3
"""Reproject original UTM RGB imagery to Web Mercator PNGs for Leaflet.
Requires GDAL CLI and rasterio/pyproj. No newspaper image is registered.
"""
import argparse,json,subprocess,tempfile
from pathlib import Path
import rasterio
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[1]
DEFAULT=Path('/Users/piyushchauhan/personal-projects/crowd-research/data/sentinel2')
def main():
 p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,default=DEFAULT);args=p.parse_args()
 out=ROOT/'dist/assets/sentinel2';out.mkdir(parents=True,exist_ok=True)
 manifest={'type':'Sentinel2OverlayManifest','source_crs':'EPSG:32644','overlay_crs':'EPSG:3857','coordinate_crs':'EPSG:4326','reference_date':'2025-01-27','attribution':'Contains modified Copernicus Sentinel data 2024–2025','method':'GDAL reprojection, bilinear resampling; RGB visualization, not surface reflectance indices. Bounds are transformed EPSG:3857 pixel edges.','images':[]}
 with tempfile.TemporaryDirectory(prefix='sangam-sentinel-') as tmp:
  for src in sorted(args.input_dir.glob('prayagraj_sangam_*.tif')):
   date=src.stem.removeprefix('prayagraj_sangam_')
   extension=ROOT/'data/sentinel2/reference-extended-2025-01-27.tif'
   if date=='2025-01-27' and extension.exists():src=extension
   warped=Path(tmp)/f'{date}.tif';png=out/f'{date}.png'
   subprocess.run(['gdalwarp','-overwrite','-t_srs','EPSG:3857','-r','bilinear','-dstalpha','-co','COMPRESS=DEFLATE',str(src),str(warped)],check=True,capture_output=True)
   subprocess.run(['gdal_translate','-of','PNG',str(warped),str(png)],check=True,capture_output=True)
   with rasterio.open(warped) as r:
    b=r.bounds;t=Transformer.from_crs(3857,4326,always_xy=True);w,s=t.transform(b.left,b.bottom);e,n=t.transform(b.right,b.top)
    manifest['images'].append({'date':date,'url':f'assets/sentinel2/{date}.png','bounds':[[s,w],[n,e]],'bbox':[w,s,e,n],'width':r.width,'height':r.height,'source_resolution_m':10,'source':f'Copernicus Sentinel-2 RGB {date}'})
   if date=='2025-01-27' and extension.exists():
    manifest['images'][-1].update({'scene_id':'S2B_44RNP_20250127_0_L2A','source_url':'https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/44/R/NP/2025/1/S2B_44RNP_20250127_0_L2A/TCI.tif','coverage_note':'Extended 6 km north using the same-date public Sentinel-2 scene; other dates retain the supplied smaller extent.'})
   aux=png.with_suffix('.png.aux.xml')
   if aux.exists():aux.unlink()
 (ROOT/'data/sentinel2').mkdir(parents=True,exist_ok=True)
 (ROOT/'data/sentinel2/manifest.json').write_text(json.dumps(manifest,indent=2))
 print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
