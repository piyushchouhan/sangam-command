#!/usr/bin/env python3
"""Check the actual serialized simulation export, independently of builder state."""
import json,pathlib,networkx as nx
R=pathlib.Path(__file__).resolve().parents[1];D=R/'data/network';load=lambda name:json.loads((D/name).read_text())
nodes=load('nodes.geojson')['features'];edges=load('edges.geojson')['features'];routes=load('routes.geojson')['features']
G=nx.Graph();G.add_nodes_from(f['id']for f in nodes);byid={f['id']:f for f in edges}
for f in edges:
 p=f['properties'];assert p['u']in G and p['v']in G;assert p['length_m']>0
 assert p['kind']in ['osm_road','mela_road','pontoon','access'];assert 'approx_width_m'in p
 G.add_edge(p['u'],p['v'])
assert nx.is_connected(G);assert len(routes)==9
for f in routes:
 p=f['properties'];assert all(n in G for n in p['node_ids']);assert all(e in byid for e in p['edge_ids'])
 assert abs(sum(byid[e]['properties']['length_m']for e in p['edge_ids'])-p['length_m'])<.1
assert next(f['properties']['length_m']for f in routes if f['properties']['station_id']=='station-sangam-station')<3000
print(f'PASS: serialized graph is connected ({len(G):,} nodes; {len(edges):,} edges), all 9 routes stay inside it and lengths reconcile.')
