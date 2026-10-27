#!/usr/bin/env python3
"""Build an auditable, undirected pedestrian planning network.

Run with /private/tmp/sangam-geo-venv/bin/python scripts/build_network.py.
OSM ways connect only by shared OSM node IDs. Temporary ground roads are
noded at geometric crossings; endpoint gaps can be snapped at most 30 m.
Pontoon interiors are never used as geometric junctions. Access connectors
are explicitly inferred, measured, and rejected if they cross mapped water.
This is a planning graph, not a certified evacuation/routing service.
"""
import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

import networkx as nx
from pyproj import Transformer
from shapely.geometry import LineString, Point, shape, mapping
from shapely.ops import transform, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Transformer.from_crs(4326, 32644, always_xy=True).transform
UNPROJECT = Transformer.from_crs(32644, 4326, always_xy=True).transform
SOURCE_ENUM = ['osm', 'traced:sentinel2-2025-01-27', 'toi_reference', 'google_maps']
CONFIDENCE_ENUM = ['high', 'medium', 'low']


def read_features(path, required=True):
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    return json.loads(path.read_text())['features']


def fid(feature, fallback):
    return str(feature.get('id') or feature.get('properties', {}).get('id') or fallback)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False))


def as_fc(name, features, **meta):
    return {'type': 'FeatureCollection', 'name': name, **meta, 'features': features}


def point_geometry(feature):
    geom = shape(feature['geometry'])
    return geom if geom.geom_type == 'Point' else geom.representative_point()


def parse_width(props):
    value = props.get('approx_width_m', props.get('width_m', props.get('tags', {}).get('width')))
    if value is None:
        return None
    try:
        number = float(str(value).lower().replace('metres', '').replace('meters', '').replace(' m', '').strip())
        return number if 0 < number < 200 else None
    except (ValueError, TypeError):
        return None


# Typical Indian urban carriageway widths (m) by OSM class, used when a way has no width/lanes tag.
OSM_CLASS_WIDTH_M = {
    'motorway': 14, 'trunk': 14, 'primary': 10, 'secondary': 7.5, 'tertiary': 7, 'unclassified': 5.5,
    'residential': 5, 'living_street': 4, 'service': 4, 'track': 3.5, 'pedestrian': 5,
    'footway': 2, 'path': 1.5, 'cycleway': 2, 'steps': 2,
    'motorway_link': 5, 'trunk_link': 5, 'primary_link': 5, 'secondary_link': 5, 'tertiary_link': 5,
}


def width_info(kind, props):
    """Width in metres with where it came from; None when nothing supports a value."""
    width = parse_width(props)
    if width is not None:
        source = props.get('width_source', 'osm_width_tag' if kind == 'osm_road' else 'source')
        return {'approx_width_m': width, 'width_source': source,
                'width_confidence': props.get('width_confidence', 'medium')}
    if kind == 'osm_road':
        tags = props.get('tags', {})
        try:
            lanes = int(float(tags.get('lanes')))
        except (TypeError, ValueError):
            lanes = None
        if lanes and 0 < lanes < 12:
            return {'approx_width_m': lanes * 3.5, 'width_source': 'osm_lanes', 'width_confidence': 'medium'}
        base = str(tags.get('highway', '')).strip()
        if base in OSM_CLASS_WIDTH_M:
            return {'approx_width_m': OSM_CLASS_WIDTH_M[base], 'width_source': 'osm_class_default', 'width_confidence': 'low'}
    return {'approx_width_m': None, 'width_source': None, 'width_confidence': None}


def ground_osm(props):
    tags = props.get('tags', {})
    return tags.get('bridge') in (None, 'no') and tags.get('tunnel') in (None, 'no') and str(tags.get('layer', '0')) in ('0', '0.0', '')


class Builder:
    def __init__(self, args):
        self.args = args
        self.nodes = {}
        self.alias = {}
        self.segments = []
        self.extra = []
        self.warnings = []
        self.rejected = []
        self.snaps = []
        self.endpoint_gaps = []
        self.input_counts = {}
        self.water = None
        self.water_source = None
        self.graph = nx.MultiGraph()
        self.features = []
        self.edge_records = {}

    def canonical(self, node):
        if node not in self.alias:
            self.alias[node] = node
        while self.alias[node] != node:
            self.alias[node] = self.alias[self.alias[node]]
            node = self.alias[node]
        return node

    def merge(self, a, b):
        a, b = self.canonical(a), self.canonical(b)
        if a == b:
            return a
        # Keep a source OSM ID whenever possible. Alias inventory preserves
        # every input ID even if an inferred ground junction joins two nodes.
        keep, drop = sorted([a, b], key=lambda n: (not n.startswith('osm-node-'), n))
        self.alias[drop] = keep
        return keep

    def node(self, ident, xy, kind='road', source='toi_reference', source_id=None):
        if ident not in self.nodes:
            self.nodes[ident] = {'xy': tuple(xy), 'kind': kind, 'source': source,
                                 'source_id': source_id or ident}
            self.alias[ident] = ident
        return ident

    def junction(self, xy, source):
        token = hashlib.sha1(f'{xy[0]:.4f},{xy[1]:.4f}'.encode()).hexdigest()[:16]
        return self.node('junction-' + token, xy, source=source)

    def split_at(self, seg, pt):
        distance = seg['geometry_m'].project(pt)
        if distance < 0.001:
            return seg['u']
        if seg['geometry_m'].length - distance < 0.001:
            return seg['v']
        node = self.junction(seg['geometry_m'].interpolate(distance).coords[0], seg['source'])
        seg['splits'].append((distance, node))
        return node

    def water_length(self, line):
        return None if self.water is None else float(line.intersection(self.water).length)

    def load_water(self):
        candidates = [self.args.water] if self.args.water else [
            ROOT / 'data/mela/river_banks.geojson', ROOT / 'data/mela/water.geojson', ROOT / 'data/sentinel2/water.geojson',
            ROOT / 'data/sentinel2/water_mask.geojson', ROOT / 'data/osm/water.geojson',
        ]
        for path in candidates:
            if path and path.exists():
                polygons = [transform(PROJECT, shape(f['geometry'])) for f in read_features(path)
                            if f.get('geometry') and shape(f['geometry']).geom_type in ('Polygon', 'MultiPolygon')]
                if polygons:
                    self.water = unary_union(polygons)
                    self.water_source = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
                    return
        self.warnings.append('No water polygon supplied. Connector water checks are unknown; routes are provisional.')

    def load_segments(self):
        inputs = [('osm_road', ROOT/'data/osm/roads.geojson'),
                  ('mela_road', ROOT/'data/mela/mela_roads.geojson'),
                  ('mela_road', ROOT/'data/mela/pontoon_approaches.geojson'),
                  ('pontoon', ROOT/'data/mela/pontoon_bridges.geojson')]
        if self.args.osm_only:
            inputs = inputs[:1]
        for kind, path in inputs:
            fs = read_features(path, required=kind == 'osm_road' or not self.args.osm_only)
            self.input_counts[kind] = self.input_counts.get(kind, 0) + len(fs)
            for fi, feature in enumerate(fs):
                p = feature.get('properties', {})
                source_id = fid(feature, f'{kind}-{fi}')
                if kind == 'osm_road' and not p.get('walkable', False):
                    continue
                if not feature.get('geometry'):
                    self.rejected.append({'source_id': source_id, 'reason': 'missing_geometry'})
                    continue
                geom = feature['geometry']
                lines = [geom['coordinates']] if geom['type'] == 'LineString' else geom['coordinates'] if geom['type'] == 'MultiLineString' else []
                if not lines:
                    self.rejected.append({'source_id': source_id, 'reason': 'not_a_line'})
                    continue
                if kind == 'osm_road' and (len(lines) != 1 or len(p.get('node_ids', [])) != len(lines[0])):
                    self.rejected.append({'source_id': source_id, 'reason': 'osm_node_coordinate_mismatch'})
                    continue
                for li, coords in enumerate(lines):
                    xy = [PROJECT(*c[:2]) for c in coords]
                    node_ids = []
                    for i, pt in enumerate(xy):
                        ident = f"osm-node-{p['node_ids'][i]}" if kind == 'osm_road' else f'{source_id}:part{li}:node{i}'
                        node_ids.append(self.node(ident, pt, source='osm' if kind == 'osm_road' else p.get('source', 'toi_reference'), source_id=source_id))
                    for i, (a, b) in enumerate(zip(xy[:-1], xy[1:])):
                        line = LineString([a, b])
                        if line.length < .001:
                            self.merge(node_ids[i], node_ids[i+1])
                            continue
                        source = 'osm' if kind == 'osm_road' else p.get('source', 'toi_reference')
                        if source not in SOURCE_ENUM:
                            source = 'toi_reference'
                        confidence = p.get('confidence', 'high' if source == 'osm' else 'low')
                        if confidence not in CONFIDENCE_ENUM:
                            confidence = 'low'
                        water_m = self.water_length(line)
                        # Temporarily traced roads cannot create new river crossings.
                        # Source OSM bridge ways and explicitly sourced pontoons can.
                        if kind == 'mela_road' and water_m is not None and water_m > self.args.water_tolerance_m:
                            self.rejected.append({'source_id': source_id, 'segment_index': i, 'reason': 'temporary_road_crosses_water', 'water_intersection_m': round(water_m, 3)})
                            continue
                        self.segments.append({
                            'id': f'{source_id}:part{li}:seg{i}', 'u': node_ids[i], 'v': node_ids[i+1],
                            'geometry_m': line, 'splits': [(0, node_ids[i]), (line.length, node_ids[i+1])],
                            'kind': kind, 'source': source, 'source_id': source_id,
                            'original_source': p.get('source', source), 'confidence': confidence,
                            'name': p.get('name', source_id), **width_info(kind, p),
                            'water_intersection_m': water_m,
                            'ground': kind == 'mela_road' or kind == 'osm_road' and ground_osm(p),
                            'is_endpoint_u': i == 0, 'is_endpoint_v': i == len(xy)-2,
                            'osm_node_ids': [p['node_ids'][i], p['node_ids'][i+1]] if kind == 'osm_road' else [],
                            'bridge': p.get('tags', {}).get('bridge'),
                            'tunnel': p.get('tags', {}).get('tunnel'),
                            'layer': p.get('tags', {}).get('layer'),
                        })

    @staticmethod
    def intersection_points(geometry):
        if geometry.is_empty:
            return []
        if geometry.geom_type == 'Point':
            return [geometry]
        if geometry.geom_type == 'MultiPoint':
            return list(geometry.geoms)
        if geometry.geom_type in ('LineString', 'LinearRing'):
            return [Point(geometry.coords[0]), Point(geometry.coords[-1])]
        if hasattr(geometry, 'geoms'):
            return [p for g in geometry.geoms for p in Builder.intersection_points(g)]
        return []

    def temporary_junctions(self):
        grounds = [s for s in self.segments if s['ground']]
        if not grounds:
            return
        tree = STRtree([s['geometry_m'] for s in grounds])
        index = {s['id']: i for i, s in enumerate(grounds)}
        crossings = 0
        # Only inferred temporary roads introduce geometric intersections.
        for seg in grounds:
            if seg['kind'] != 'mela_road':
                continue
            for j in tree.query(seg['geometry_m'], predicate='intersects'):
                other = grounds[int(j)]
                if other['id'] == seg['id'] or other['kind'] == 'mela_road' and index[other['id']] < index[seg['id']]:
                    continue
                for pt in self.intersection_points(seg['geometry_m'].intersection(other['geometry_m'])):
                    self.merge(self.split_at(seg, pt), self.split_at(other, pt))
                    crossings += 1
        self.input_counts['temporary_ground_crossing_joins'] = crossings
        # Endpoint snapping connects only actual endpoints, never a pontoon
        # middle to a geometrically crossing road or another bridge.
        seen = set()
        for seg in self.segments:
            if seg['kind'] not in ('mela_road', 'pontoon'):
                continue
            for side in ('u', 'v'):
                if not seg['is_endpoint_' + side]:
                    continue
                endpoint = seg[side]
                if endpoint in seen:
                    continue
                seen.add(endpoint)
                pt = Point(self.nodes[endpoint]['xy'])
                candidates = []
                for j in tree.query(pt.buffer(self.args.snap_m)):
                    other = grounds[int(j)]
                    if other['source_id'] == seg['source_id']:
                        continue
                    q = other['geometry_m'].interpolate(other['geometry_m'].project(pt))
                    dist = pt.distance(q)
                    if dist <= self.args.snap_m:
                        candidates.append((dist, other['id'], other, q))
                for dist, _, other, q in sorted(candidates, key=lambda c: (c[0], c[1])):
                    line = LineString([pt, q])
                    water_m = self.water_length(line)
                    if water_m is not None and water_m > self.args.water_tolerance_m:
                        continue
                    target = self.split_at(other, q)
                    if dist <= .001:
                        self.merge(endpoint, target)
                    elif self.canonical(endpoint) != self.canonical(target):
                        self.extra.append({'id': f'snap-{endpoint}', 'u': endpoint, 'v': target,
                            'geometry_m': line, 'kind': 'access', 'source': other['source'],
                            'source_id': seg['source_id'], 'original_source': 'endpoint_snap',
                            'confidence': 'low', 'name': 'Inferred endpoint snap',
                            'approx_width_m': None, 'water_intersection_m': water_m,
                            'access_type': 'endpoint_snap', 'method': 'inferred_endpoint_snap', 'snap_distance_m': dist})
                    self.snaps.append({'source_id': seg['source_id'], 'endpoint_id': endpoint,
                                       'target_source_id': other['source_id'], 'distance_m': round(dist, 3)})
                    break
                else:
                    self.warnings.append(f'No water-safe road endpoint snap within {self.args.snap_m:g} m for {endpoint}.')
                    nearby = []
                    for j in tree.query(pt.buffer(2000)):
                        other = grounds[int(j)]
                        if other['source_id'] == seg['source_id']:
                            continue
                        q = other['geometry_m'].interpolate(other['geometry_m'].project(pt))
                        distance = pt.distance(q)
                        nearby.append((distance, other['id'], other, q))
                    nearest = []
                    for distance, _, other, q in sorted(nearby, key=lambda c: (c[0], c[1]))[:3]:
                        water_m = self.water_length(LineString([pt, q]))
                        nearest.append({'source_id': other['source_id'], 'segment_id': other['id'],
                                        'distance_m': round(distance, 3),
                                        'road_coordinates': list(UNPROJECT(*q.coords[0])),
                                        'road_epsg32644': list(q.coords[0]),
                                        'road_raster_pixel': [(q.x - 582420) / 10, (2817890 - q.y) / 10],
                                        'water_intersection_m': None if water_m is None else round(water_m, 3)})
                    self.endpoint_gaps.append({'source_id': seg['source_id'], 'kind': seg['kind'],
                        'endpoint_id': endpoint, 'coordinates': list(UNPROJECT(*pt.coords[0])),
                        'epsg32644': list(pt.coords[0]),
                        'raster_pixel': [(pt.x - 582420) / 10, (2817890 - pt.y) / 10],
                        'nearest_ground_road_candidates': nearest,
                        'reason': 'no_water_safe_road_within_30m',
                        'action': 'Inspect source imagery for an actual approach; no connector was invented.'})

    def add_graph_edge(self, record):
        u, v = self.canonical(record['u']), self.canonical(record['v'])
        if u == v:
            return
        geom = record['geometry_m']
        if geom.length < .001:
            return
        for n in (u, v):
            if n not in self.graph:
                data = self.nodes[n]
                lon, lat = UNPROJECT(*data['xy'])
                self.graph.add_node(n, lon=lon, lat=lat, x_m=data['xy'][0], y_m=data['xy'][1],
                                    kind=data['kind'], source=data['source'], source_id=data['source_id'],
                                    confidence='high' if data['source'] == 'osm' and n.startswith('osm-node-') else 'low')
        props = {k: v for k, v in record.items() if k not in ('geometry_m', 'splits', 'ground', 'is_endpoint_u', 'is_endpoint_v')}
        props.update(u=u, v=v, length_m=round(geom.length, 3))
        if props.get('water_intersection_m') is not None:
            props['water_intersection_m'] = round(props['water_intersection_m'], 3)
        coordinates = [list(UNPROJECT(*xy)) for xy in geom.coords]
        feature = {'type': 'Feature', 'id': record['id'], 'geometry': {'type': 'LineString', 'coordinates': coordinates}, 'properties': props}
        self.edge_records[record['id']] = feature
        self.graph.add_edge(u, v, key=record['id'], **props)

    def assemble_graph(self):
        for seg in self.segments:
            splits = sorted(seg['splits'], key=lambda x: x[0])
            clean = []
            for distance, node in splits:
                if clean and abs(clean[-1][0] - distance) < .001:
                    self.merge(clean[-1][1], node)
                else:
                    clean.append((distance, node))
            for i, ((start, u), (end, v)) in enumerate(zip(clean[:-1], clean[1:])):
                if end-start < .001:
                    continue
                record = dict(seg)
                record.update(id=seg['id'] if len(clean) == 2 else seg['id'] + f':split{i}',
                              u=u, v=v, geometry_m=LineString([seg['geometry_m'].interpolate(start), seg['geometry_m'].interpolate(end)]))
                record['water_intersection_m'] = self.water_length(record['geometry_m'])
                self.add_graph_edge(record)
        for edge in self.extra:
            self.add_graph_edge(edge)

    def attach_features(self):
        if self.args.osm_only:
            return
        nose = read_features(ROOT/'data/mela/sangam_nose.geojson')
        groups = [('sangam', nose),
                  ('station', read_features(ROOT/'data/osm/stations_normalized.geojson')),
                  ('parking', read_features(ROOT/'data/mela/parking.geojson')),
                  ('sector', read_features(ROOT/'data/mela/sectors.geojson'))]
        # Road nodes, excluding bridge/tunnel-only vertices, are plausible
        # access attachment points. The nearest road is tried first.
        road_nodes = set()
        for seg in self.segments:
            if seg['ground']:
                road_nodes.update(self.canonical(n) for _, n in seg['splits'])
        road_nodes = sorted(road_nodes.intersection(self.graph))
        points = [Point(self.nodes[n]['xy']) for n in road_nodes]
        tree = STRtree(points)
        self.destination = None
        reachable = None
        for kind, fs in groups:
            self.input_counts[kind] = self.input_counts.get(kind, 0) + len(fs)
            for i, f in enumerate(fs):
                ident = fid(f, f'{kind}-{i}')
                p = f.get('properties', {})
                info = {'id': ident, 'kind': kind, 'name': p.get('name', ident),
                        'status': 'unresolved', 'access_node_id': None, 'road_node_id': None,
                        'access_length_m': None, 'water_intersection_m': None,
                        'geometry_resolved': bool(f.get('geometry'))}
                if not f.get('geometry'):
                    info['reason'] = 'missing_geometry'
                    self.features.append(info)
                    continue
                point = transform(PROJECT, point_geometry(f))
                access_id = f'access:{ident}'
                self.node(access_id, point.coords[0], kind=kind, source=p.get('source') if p.get('source') in SOURCE_ENUM else 'toi_reference', source_id=ident)
                # Search within a bounded access distance. Reachable nodes are
                # preferred only among water-safe candidates; this never joins
                # two road components because an access point has one edge.
                candidates = [(point.distance(points[int(j)]), road_nodes[int(j)], points[int(j)])
                              for j in tree.query(point.buffer(self.args.max_access_m))]
                candidates.sort(key=lambda v: (v[0], v[1]))
                selected = None
                blocked_water = 0
                closest_safe = None
                for distance, target, target_point in candidates:
                    if distance > self.args.max_access_m:
                        continue
                    line = LineString([point, target_point])
                    water_m = self.water_length(line)
                    if water_m is not None and water_m > self.args.water_tolerance_m:
                        blocked_water += 1
                        continue
                    if closest_safe is None:
                        closest_safe = (distance, target, line, water_m)
                    if reachable is None or target in reachable:
                        selected = (distance, target, line, water_m)
                        break
                selected = selected or closest_safe
                if selected is None:
                    info.update(reason='no_water_safe_road_within_access_limit', water_blocked_candidates=blocked_water)
                    self.features.append(info)
                    continue
                distance, target, line, water_m = selected
                confidence = 'low'
                if distance < .001:
                    self.merge(access_id, target)
                    access_id = self.canonical(target)
                else:
                    self.add_graph_edge({'id': f'access-edge:{ident}', 'u': access_id, 'v': target,
                        'geometry_m': line, 'kind': 'access', 'source': p.get('source') if p.get('source') in SOURCE_ENUM else self.graph.nodes[target]['source'],
                        'source_id': ident, 'original_source': 'point_to_road_access',
                        'confidence': confidence, 'name': f'Inferred {kind} access: {p.get("name", ident)}',
                        'approx_width_m': None, 'water_intersection_m': water_m,
                        'access_type': kind, 'method': 'inferred_point_to_road_access', 'long_connector': distance > self.args.long_access_m,
                        'source_point_method': 'source_point' if f['geometry']['type'] == 'Point' else 'polygon_representative_point'})
                info.update(status='attached', access_node_id=access_id, road_node_id=target,
                            access_length_m=round(distance, 3), confidence=confidence,
                            long_connector=distance > self.args.long_access_m,
                            water_intersection_m=None if water_m is None else round(water_m, 3),
                            coordinates=list(UNPROJECT(*point.coords[0])))
                self.features.append(info)
                if kind == 'sangam' and self.destination is None:
                    self.destination = access_id
                    reachable = nx.node_connected_component(self.graph, self.destination)

    def validate_and_routes(self):
        g = self.graph
        components = sorted(nx.connected_components(g), key=len, reverse=True)
        component_of = {node: i for i, c in enumerate(components) for node in c}
        for n, cid in component_of.items():
            g.nodes[n]['component_id'] = cid
        self.routes = []
        destination = getattr(self, 'destination', None)
        distances, paths = nx.single_source_dijkstra(g, destination, weight='length_m') if destination in g else ({}, {})
        for f in self.features:
            node = f['access_node_id']
            f['reachable_to_sangam'] = node in distances
            f['shortest_distance_m'] = round(distances[node], 3) if node in distances else None
            f['component_id'] = component_of.get(node)
            if f['kind'] != 'station' or node not in paths:
                continue
            ordered_nodes = list(reversed(paths[node]))
            coordinates = []
            edge_ids = []
            low_edges = 0
            water_unknown = 0
            kinds = collections.Counter()
            for u, v in zip(ordered_nodes[:-1], ordered_nodes[1:]):
                key, edge = min(g[u][v].items(), key=lambda kv: (kv[1]['length_m'], kv[0]))
                edge_ids.append(key)
                low_edges += edge['confidence'] == 'low'
                water_unknown += edge.get('water_intersection_m') is None
                kinds[edge['kind']] += edge['length_m']
                cs = self.edge_records[key]['geometry']['coordinates']
                if edge['u'] != u:
                    cs = list(reversed(cs))
                coordinates.extend(cs if not coordinates else cs[1:])
            props = {'id': f'route:{f["id"]}:sangam', 'station_id': f['id'],
                     'name': f['name'] + ' to Sangam', 'destination_node_id': destination,
                     'length_m': f['shortest_distance_m'], 'source': 'traced:sentinel2-2025-01-27', 'sources': ['osm','traced:sentinel2-2025-01-27'], 'confidence': 'low',
                     'method': 'derived_shortest_path_from_multiple_sources',
                     'edge_ids': edge_ids, 'node_ids': ordered_nodes, 'low_confidence_edges': low_edges,
                     'water_unknown_edges': water_unknown, 'length_by_kind_m': {k: round(v,3) for k,v in kinds.items()},
                     'planning_only': True, 'algorithm': 'Dijkstra; undirected pedestrian length_m'}
            self.routes.append({'type': 'Feature', 'id': props['id'], 'geometry': {'type': 'LineString', 'coordinates': coordinates}, 'properties': props})
        by_kind = {}
        for kind in ('station', 'parking', 'sector', 'sangam'):
            rows = [f for f in self.features if f['kind'] == kind]
            by_kind[kind] = {'total': len(rows), 'resolved_geometry_and_access': sum(r['status'] == 'attached' for r in rows),
                             'reachable': sum(r['reachable_to_sangam'] for r in rows),
                             'unreachable_ids': [r['id'] for r in rows if not r['reachable_to_sangam']]}
        road_snap_max = max((s['distance_m'] for s in self.snaps), default=0)
        pontoon_endpoints = collections.defaultdict(set)
        for s in self.segments:
            if s['kind'] == 'pontoon':
                for side in ('u', 'v'):
                    if s['is_endpoint_' + side]:
                        pontoon_endpoints[s['source_id']].add(s[side])
        snapped_endpoints = {s['endpoint_id'] for s in self.snaps}
        pontoon_connectivity = [{'id': ident, 'observed_endpoints': len(endpoints),
                                'attached_endpoints': len(endpoints.intersection(snapped_endpoints)),
                                'both_ends_connected_to_road': endpoints.issubset(snapped_endpoints)}
                               for ident,endpoints in sorted(pontoon_endpoints.items())]
        access_water = [e['properties']['water_intersection_m'] for e in self.edge_records.values() if e['properties']['kind'] == 'access' and e['properties'].get('water_intersection_m') is not None]
        tests = {
            'all_9_stations_loaded': by_kind['station']['total'] == 9,
            'all_9_station_routes_exist': by_kind['station']['reachable'] == 9 and len(self.routes) == 9,
            'all_resolved_parking_reachable': all(f['reachable_to_sangam'] for f in self.features if f['kind'] == 'parking' and f['geometry_resolved']),
            'all_25_sectors_reachable': by_kind['sector']['total'] == 25 and by_kind['sector']['reachable'] == 25,
            'all_endpoint_snaps_within_30m': road_snap_max <= 30,
            'all_observed_pontoon_endpoints_connected': all(p['both_ends_connected_to_road'] for p in pontoon_connectivity),
            'no_access_water_crossings_above_tolerance': self.water is not None and max(access_water, default=0) <= self.args.water_tolerance_m,
            'no_negative_or_zero_edge_lengths': all(e['properties']['length_m'] > 0 for e in self.edge_records.values()),
            'edge_endpoints_exist': all(e['properties']['u'] in g and e['properties']['v'] in g for e in self.edge_records.values()),
            'all_sources_and_confidences_in_enum': all(e['properties']['source'] in SOURCE_ENUM and e['properties']['confidence'] in CONFIDENCE_ENUM for e in self.edge_records.values()),
        }
        route_validation = []
        for r in self.routes:
            p = r['properties']
            total = sum(self.edge_records[e]['properties']['length_m'] for e in p['edge_ids'])
            node_path = p['node_ids']
            contiguous = all(g.has_edge(u,v,key=k) for u,v,k in zip(node_path[:-1], node_path[1:],p['edge_ids']))
            route_validation.append({'station_id': p['station_id'], 'contiguous': contiguous,
                                     'length_matches_edges': abs(total-p['length_m']) < .01,
                                     'dijkstra_shortest_verified': abs(nx.shortest_path_length(g,node_path[0],destination,weight='length_m')-p['length_m']) < .01})
        tests['all_generated_routes_contiguous_and_shortest'] = all(all(v for k,v in t.items() if k != 'station_id') for t in route_validation)
        self.validation = {
            'schema_version': 1, 'crs': 'EPSG:4326', 'measurement_crs': 'EPSG:32644',
            'graph_type': 'undirected MultiGraph; pedestrian planning only',
            'source_enum': SOURCE_ENUM, 'confidence_enum': CONFIDENCE_ENUM,
            'inputs': self.input_counts, 'nodes': len(g), 'edges': g.number_of_edges(),
            'components': len(components), 'component_sizes': [len(c) for c in components],
            'destination_node_id': destination, 'water_source': self.water_source,
            'parameters': {'endpoint_snap_max_m': self.args.snap_m, 'max_access_m': self.args.max_access_m,
                           'long_access_threshold_m': self.args.long_access_m, 'water_tolerance_m': self.args.water_tolerance_m},
            'reachability': by_kind, 'features': self.features, 'tests': tests,
            'route_tests': route_validation, 'rejected_segments': self.rejected,
            'unresolved_features': [f for f in self.features if f['status'] != 'attached'] +
                                   [f for f in self.rejected if f['reason'] == 'missing_geometry'],
            'endpoint_snaps': self.snaps, 'endpoint_gaps': self.endpoint_gaps,
            'pontoon_connectivity': pontoon_connectivity, 'warnings': self.warnings,
            'limitations': [
                'OSM metadata is not a field verification of present pedestrian permissions.',
                'Temporary Mela geometry and access connectors are planning interpretations of their cited source.',
                'Widths are approximate: OSM width/lanes tags, OSM class defaults, mela roads measured on Google Maps satellite, pontoons estimated at 5 m. width_source says which; null means unavailable. No capacities are invented.',
                'Station and parking source points are connected by inferred straight access segments, not surveyed entrances.',
                'Sector access uses a polygon representative point; this is not an established gate.',
                'Disconnected components are preserved; no long edge joins components merely to satisfy a routing test.',
                'Road and bridge operation, crowd direction, closures, and emergency suitability require separate verification.',
            ],
        }

    def write(self):
        out = ROOT/'data/network'
        out.mkdir(parents=True, exist_ok=True)
        aliases = collections.defaultdict(list)
        for n in self.nodes:
            if self.canonical(n) != n:
                aliases[self.canonical(n)].append(n)
        nodes = []
        for ident, p in self.graph.nodes(data=True):
            props = dict(p)
            props.update(id=ident, original_node_ids=aliases.get(ident, []))
            props.pop('x_m', None)
            props.pop('y_m', None)
            nodes.append({'type': 'Feature', 'id': ident, 'geometry': {'type': 'Point', 'coordinates': [p['lon'],p['lat']]}, 'properties': props})
        meta = {'measurement_crs': 'EPSG:32644', 'source_enum': SOURCE_ENUM, 'confidence_enum': CONFIDENCE_ENUM, 'planning_only': True}
        connected = nx.node_connected_component(self.graph, self.destination)
        main_edges = [f for f in self.edge_records.values() if f['properties']['u'] in connected and f['properties']['v'] in connected]
        detached_edges = [f for f in self.edge_records.values() if f['properties']['u'] not in connected]
        write_json(out/'nodes.geojson', as_fc('sangam_connected_nodes', [f for f in nodes if f['id'] in connected], **meta))
        write_json(out/'edges.geojson', as_fc('sangam_connected_edges', main_edges, **meta))
        write_json(out/'disconnected_nodes.geojson', as_fc('detached_candidate_nodes', [f for f in nodes if f['id'] not in connected], **meta))
        write_json(out/'disconnected_edges.geojson', as_fc('detached_candidate_edges', detached_edges, **meta))
        self.validation['full_graph_components'] = self.validation['components']
        self.validation['canonical_export'] = {'components':1,'nodes':len(connected),'edges':len(main_edges),'selection':'Sangam-connected component; detached geometry retained separately'}
        write_json(out/'routes.geojson', as_fc('station_to_sangam_planning_routes', self.routes, **meta))
        write_json(out/'validation.json', self.validation)
        write_json(out/'pontoon_gaps.json', {
            'measurement_crs': 'EPSG:32644',
            'raster_pixel_formula': 'x=(easting-582420)/10; y=(2817890-northing)/10',
            'maximum_endpoint_snap_m': self.args.snap_m,
            'gaps': [g for g in self.endpoint_gaps if g['kind'] == 'pontoon'],
            'connectivity': self.validation['pontoon_connectivity'],
        })
        # Render-only geometry groups primitive graph segments by original
        # source feature. No topology is changed in the authoritative exports.
        render_groups = collections.defaultdict(list)
        render_properties = {}
        for f in self.edge_records.values():
            p = f['properties']
            group = (p['source_id'], p['kind'])
            render_groups[group].append(f['geometry']['coordinates'])
            render_properties[group] = {k: p.get(k) for k in ('source_id','kind','source','confidence','name','approx_width_m','width_source')}
        renders = []
        for group, lines in render_groups.items():
            p = render_properties[group]
            p['id'] = f'render:{group[0]}:{group[1]}'
            # Coordinates rounded to about 0.1 m, below imagery uncertainty.
            lines = [[[round(x,6), round(y,6)] for x,y in line] for line in lines]
            renders.append({'type':'Feature','id':p['id'],'properties':p,
                            'geometry':{'type':'MultiLineString','coordinates':lines}})
        write_json(out/'render_edges.geojson', as_fc('render_only_network_edges', renders, **meta))
        # GraphML lacks null/list/object values; omit nulls and serialize lists.
        serial = nx.MultiGraph()
        serial.graph.update(crs='EPSG:4326', measurement_crs='EPSG:32644', planning_only=True)
        def safe(d):
            return {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list,dict)) else v
                    for k,v in d.items() if v is not None}
        serial.add_nodes_from((n,safe(d)) for n,d in self.graph.nodes(data=True) if n in connected)
        serial.add_edges_from((u,v,k,safe(d)) for u,v,k,d in self.graph.edges(keys=True,data=True) if u in connected and v in connected)
        nx.write_graphml(serial, out/'graph.graphml', named_key_ids=True)
        print(json.dumps({'output': str(out), 'nodes': len(self.graph), 'edges': self.graph.number_of_edges(),
                          'components': self.validation['components'], 'reachability': self.validation['reachability'],
                          'tests': self.validation['tests'], 'rejected_segments': len(self.rejected)}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--osm-only', action='store_true', help='Audit/build only available OSM roads before Mela input layers exist.')
    parser.add_argument('--water', type=Path, help='Polygon GeoJSON used to reject access/temporary-road water crossings.')
    parser.add_argument('--snap-m', type=float, default=30)
    parser.add_argument('--max-access-m', type=float, default=1500)
    parser.add_argument('--long-access-m', type=float, default=100)
    parser.add_argument('--water-tolerance-m', type=float, default=.1)
    args = parser.parse_args()
    if not 0 <= args.snap_m <= 30:
        parser.error('--snap-m must be between 0 and 30 m')
    builder = Builder(args)
    builder.load_water()
    builder.load_segments()
    builder.temporary_junctions()
    builder.assemble_graph()
    builder.attach_features()
    builder.validate_and_routes()
    builder.write()


if __name__ == '__main__':
    main()
