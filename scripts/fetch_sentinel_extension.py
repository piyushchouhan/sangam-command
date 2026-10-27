#!/usr/bin/env python3
"""Obtain northern coverage from the same public Jan27 Sentinel-2 scene."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'data/sentinel2/reference-extended-2025-01-27.tif';out.parent.mkdir(parents=True,exist_ok=True)
url='https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/44/R/NP/2025/1/S2B_44RNP_20250127_0_L2A/TCI.tif'
subprocess.run(['gdal_translate','-projwin','582420','2823890','595570','2808380','-co','COMPRESS=DEFLATE','/vsicurl/'+url,str(out)],check=True)
print(out)
