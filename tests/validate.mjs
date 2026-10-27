import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const map=JSON.parse(fs.readFileSync('dist/map-data.json','utf8'));
assert.equal(map.coordinateSystem.crs,'EPSG:4326');
assert.equal(map.coordinateSystem.georeferenced,true);
assert.equal(new Set(map.features.map(f=>f.id)).size,map.features.length);
assert.equal(map.features.filter(f=>f.type==='sector').length,25);
assert.equal(map.features.filter(f=>f.type==='station').length,9);
const legacyIds=JSON.parse(fs.readFileSync('tests/legacy-ids.json','utf8'));
for(const id of legacyIds)assert.ok(map.features.some(f=>f.id===id),`Saved ID lost: ${id}`);
function coords(c){if(typeof c[0]==='number'){assert.ok(c[0]>81.6&&c[0]<82.1&&c[1]>25.2&&c[1]<25.7);return}c.forEach(coords)}
for(const f of map.features){assert.ok(!('xy'in f)&&!('polygon'in f)&&!('line'in f));assert.ok(['osm','traced:sentinel2-2025-01-27','toi_reference','google_maps'].includes(f.source));assert.ok(['low','medium','high'].includes(f.confidence));if(f.geometry)coords(f.geometry.coordinates);else{assert.equal(f.confidence,'low');assert.equal(f.coordinates,null)}}
assert.ok(!fs.existsSync('dist/assets/source-map.jpg')&&!fs.existsSync('dist/assets/source-map.pdf'));
assert.equal(map.statistics.parking.currentHectares+map.statistics.parking.newHectares,map.statistics.parking.totalHectares);
const context=vm.createContext({console,Date,Math,Set,JSON,Number,Object,String,Array});
vm.runInContext(fs.readFileSync('dist/app.js','utf8').replace(/init\(\);\s*$/,''),context);
context.sourceMap=map;
vm.runInContext('data=sourceMap',context);
const base={schemaVersion:1,sectors:{},incidents:[],markers:[]};
function validate(o){context.candidate=o;return vm.runInContext('validateWorkspace(candidate)',context)}
assert.equal(Object.keys(validate(base).sectors).length,0);
const one=structuredClone(base);one.sectors['sector-06']={count:0,capacity:100,status:'monitor',team:'Team A',notes:'Test',updatedAt:new Date().toISOString()};
assert.equal(validate(one).sectors['sector-06'].count,0,'zero must survive roundtrip');
assert.equal(validate({schemaVersion:1,map,workspace:one}).sectors['sector-06'].capacity,100);
for(const patch of [{count:-1},{count:0.5},{capacity:0},{status:'invented'},{updatedAt:'bad-date'}]){const bad=structuredClone(one);Object.assign(bad.sectors['sector-06'],patch);assert.throws(()=>validate(bad))}
const m=structuredClone(base);m.markers.push({id:'custom-test',name:'Test gate',kind:'Gate',type:'custom',description:'',xy:[500,500],updatedAt:new Date().toISOString()});assert.equal(validate(m).markers.length,1);assert.equal(validate(m).markers[0].coordinates,null);assert.equal(validate(m).markers[0].legacy_location.xy[0],500);assert.equal(validate(m).schemaVersion,2);const again=validate(JSON.parse(JSON.stringify(validate(m))));assert.equal(again.markers[0].legacy_location.xy[1],500);
m.markers[0].xy=[-1,500];assert.throws(()=>validate(m));
const invalid=structuredClone(base);invalid.incidents=[{id:'a',featureId:'nonexistent',title:'Missing reference',description:'',severity:'high',status:'open',createdAt:new Date().toISOString()}];assert.throws(()=>validate(invalid));
const modern=structuredClone(base);modern.schemaVersion=2;modern.markers=[{id:'custom-geo',name:'Gate',kind:'Gate',type:'custom',description:'',coordinates:[81.89,25.44]}];assert.equal(validate(modern).markers[0].geometry.type,'Point');modern.markers[0].coordinates=[500,500];assert.throws(()=>validate(modern));
console.log('PASS: WGS84 geometry, provenance, 108 stable legacy IDs, copyright exclusion, v1/v2 migration, zero/unknown values, import validation.');
