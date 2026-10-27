#!/usr/bin/env python3
"""Package the connected graph and its audit; no source imagery or personal workspace."""
import pathlib,zipfile,json
R=pathlib.Path(__file__).resolve().parents[1];out=R/'dist/data/network/network.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=7)as z:
 for name in ['nodes.geojson','edges.geojson','graph.graphml','routes.geojson','validation.json','disconnected_nodes.geojson','disconnected_edges.geojson','pontoon_gaps.json']:
  z.write(R/'data/network'/name,'network/'+name)
 z.writestr('README.txt','Connected Sangam research graph. WGS84 lon/lat; length_m measured in UTM44N. OSM © OpenStreetMap contributors (ODbL); contains modified Copernicus Sentinel data2024–2025. Access edges are inferred, widths may be unknown. See validation.json: not every observed pontoon has both approaches, and 3 bridge slots remain unlocated. Not a validated JuPedSim walkable polygon or operational evacuation model. Detached candidates are kept separately, never joined by invented edges.\n')
print(f'{out}: {out.stat().st_size/1e6:.1f} MB')
