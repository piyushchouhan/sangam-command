'use strict';
// Data is RFC 7946 lon/lat. Leaflet projects into Web Mercator for OSM tiles.
class SangamMap {
  constructor({onSelect,onPlace,onReady}) {this.onSelect=onSelect;this.onPlace=onPlace;this.onReady=onReady;this.routeIndex=new Map();this.datasets={};this.layers={};this.lowOnly=false;this.date='2025-01-27';this.currentMode='clean';this.placement=false;}
  async init(atlas){
    if(!window.L)throw Error('Leaflet could not load. Check the CDN or local vendor fallback.');
    this.atlas=atlas;this.map=L.map('map',{zoomControl:false,preferCanvas:true,maxZoom:20,minZoom:10}).setView([25.456,81.89],13);
    this.renderer=L.canvas({padding:.3});this.features=L.layerGroup().addTo(this.map);this.labels=L.layerGroup().addTo(this.map);this.routeHighlight=L.geoJSON(null,{renderer:this.renderer,style:{color:'#dc6c32',weight:6,opacity:.95}}).addTo(this.map);
    this.map.createPane('satellite');this.map.getPane('satellite').style.zIndex=250;
    this.tiles=L.tileLayer(atlas.basemap.url,{maxZoom:19,attribution:'<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors (ODbL)</a>'}).addTo(this.map);
    L.control.scale({imperial:false,position:'bottomleft'}).addTo(this.map);
    this.map.attributionControl.addAttribution('Contains modified Copernicus Sentinel data 2024–2025');
    this.map.on('click',e=>{if(this.placement)this.onPlace({coordinates:[e.latlng.lng,e.latlng.lat]});});
    this.map.on('zoomend',()=>this.drawLabels());
    new ResizeObserver(()=>this.map.invalidateSize({pan:false})).observe(document.querySelector('#map-canvas'));
    const manifest=await this.fetchJSON(atlas.datasets.sentinel);this.manifest=manifest;
    const select=document.querySelector('#satellite-date');select.innerHTML=manifest.images.map(i=>`<option value="${i.date}" ${i.date===this.date?'selected':''}>${i.date}${i.date==='2024-10-19'?' · baseline':''}</option>`).join('');select.onchange=()=>{this.date=select.value;setMode('overlay')};
    this.fit();
    this.fetchJSON(atlas.datasets.routes).then(d=>{this.datasets.routes=d;d.features.forEach(f=>this.routeIndex.set(f.properties.station_id||f.properties.id,f));this.onReady?.()}).catch(()=>{});
    this.fetchJSON(atlas.datasets.validation).then(d=>{this.validation=d;this.onReady?.()}).catch(()=>{});
    this.checkLocalReference();
  }
  async fetchJSON(url){const r=await fetch(url,{cache:'no-cache'});if(!r.ok)throw Error(`Unable to load ${url}`);return r.json()}
  fit(){const g=this.atlas.features.filter(f=>f.type==='sector'&&f.geometry).map(f=>({type:'Feature',geometry:f.geometry,properties:{}}));const bounds=L.geoJSON({type:'FeatureCollection',features:g}).getBounds();if(bounds.isValid())this.map.fitBounds(bounds,{padding:[24,24]})}
  focus(f){if(!f.geometry){toast('This reference has no verified geographic location yet.');return}const layer=L.geoJSON({type:'Feature',geometry:f.geometry,properties:{}});const bounds=layer.getBounds();if(f.geometry.type==='Point')this.map.setView([f.coordinates[1],f.coordinates[0]],16);else this.map.fitBounds(bounds,{padding:[40,40],maxZoom:17})}
  placementMode(enabled){this.placement=enabled;this.map.getContainer().classList.toggle('placing',enabled)}
  routeFor(id){return this.routeIndex.get(id)}
  showRoute(id){const route=this.routeFor(id);if(!route){toast('No verified graph route is available for this feature.');return}this.routeHighlight.clearLayers().addData(route);this.map.fitBounds(this.routeHighlight.getBounds(),{padding:[25,25]});}
  clearRoute(){this.routeHighlight.clearLayers()}
  async checkLocalReference(){const btn=document.querySelector('[data-mode="original"]');this.localReference=false;if(!['localhost','127.0.0.1','::1'].includes(location.hostname)){btn.title='Local reference only; not deployed';return}try{const r=await fetch('/__local_reference__/source-map.jpg',{method:'HEAD'});this.localReference=r.ok&&r.headers.get('content-type')?.startsWith('image/');}catch{}btn.title=this.localReference?'Open unregistered local reference':'Run scripts/serve_local.py to inspect the local reference';}
  async setMode(mode){
    if(mode==='original'){if(!this.localReference){toast('Original is local-only. Run scripts/serve_local.py with local-reference/source-map.jpg present.');return false}modal('<h2>Local newspaper reference</h2><p>Unregistered reference for sector numbering and adjacency only. It is not overlaid on the geographic map.</p><img class="local-reference-image" src="/__local_reference__/source-map.jpg" alt="Local TOI reference map"><div class="modal-actions"><button class="button" data-close>Close</button></div>');return false}
    this.currentMode=mode;this.satellite?.remove();
    if(mode==='overlay'){const image=this.manifest.images.find(i=>i.date===this.date);this.satellite=L.imageOverlay(image.url,image.bounds,{pane:'satellite',opacity:1,interactive:false}).addTo(this.map);}
    document.querySelector('#map-mode-label').textContent=mode==='overlay'?`Sentinel-2 · ${this.date} · 10 m`:'WGS84 coordinates · OSM basemap';return true;
  }
  popup(f){return `<strong>${esc(f.name)}</strong><br>Source: ${esc(f.source||'user')}<br>Confidence: ${esc(f.confidence||'low')}${f.area_ha!=null?`<br>Area: ${Number(f.area_ha).toFixed(2)} ha`:''}${f.approx_width_m?`<br>Width: ~${f.approx_width_m} m (${esc((f.width_source||'').replace(/_/g,' '))})`:''}`}
  color(f){return {station:'#647b73',landmark:'#b78c54',parking_area:'#819b63',parking:'#819b63',police:'#586ca4',water:'#669da8',crossing:'#bc7352',custom:'#a3724e'}[f.type]||'#7b8f7a'}
  render(features,visible,selected,operations){
    if(!this.map)return;this.features.clearLayers();this.labels.clearLayers();this.last={features,visible,selected,operations};
    const statusColors={normal:'#4d8460',monitor:'#bd9a45',restricted:'#bd7051',closed:'#ac5048'};
    for(const f of features){if(!f.geometry||!visible.has(f.type==='parking_area'?'parking':f.type)||(this.lowOnly&&f.confidence!=='low'))continue;
      const active=f.id===selected;const fc={type:'Feature',geometry:f.geometry,properties:f};
      const layer=L.geoJSON(fc,{renderer:this.renderer,style:()=>{if(f.type==='sector')return {color:active?'#1f503e':'#617f58',weight:active?3:1.2,fillColor:active?'#c9dc9d':['#d8e5ca','#e4e7cb','#cee1d2'][f.number%3],fillOpacity:this.currentMode==='overlay'?.15:.35,dashArray:f.confidence==='low'?'5 4':null};return {color:this.color(f),weight:f.type==='crossing'?3:1.5,fillOpacity:f.type==='water'?.35:.3,dashArray:f.confidence==='low'?'5 4':null}},pointToLayer:(_f,ll)=>L.circleMarker(ll,{radius:f.type==='station'?7:5,color:'#fff',weight:1.5,fillColor:this.color(f),fillOpacity:1})});
      layer.bindTooltip(this.popup(f),{sticky:true,className:'geo-tooltip'});layer.on('click',e=>{if(this.placement)return;L.DomEvent.stopPropagation(e);this.onSelect(f.id);L.popup({maxWidth:260}).setLatLng(e.latlng).setContent(this.popup(f)).openOn(this.map)});layer.bindPopup(this.popup(f),{maxWidth:260});layer.addTo(this.features);
    }
    this.drawLabels();this.syncDatasets(visible);
  }
  drawLabels(){if(!this.last)return;this.labels.clearLayers();const{features,visible,selected,operations}=this.last;
    for(const f of features){if(!f.geometry||!f.coordinates||!visible.has(f.type==='parking_area'?'parking':f.type)||(this.lowOnly&&f.confidence!=='low'))continue;
      if(f.type==='sector'){const state=operations[f.id]?.status;const icon=L.divIcon({className:'geo-sector-icon',html:`<span class="geo-sector-label ${f.id===selected?'selected':''}">${f.number}${state&&state!=='unknown'?`<i class="status-${esc(state)}"></i>`:''}</span>`,iconSize:[30,26],iconAnchor:[15,13]});L.marker([f.coordinates[1],f.coordinates[0]],{icon,keyboard:true,title:f.name}).on('click',()=>{if(!this.placement)this.onSelect(f.id)}).addTo(this.labels)}
      else if(f.type==='station'||(this.map.getZoom()>=15&&['landmark','police','custom'].includes(f.type))){const icon=L.divIcon({className:'geo-name-icon',html:`<span>${esc(f.name)}</span>`,iconSize:[160,18],iconAnchor:[-9,9]});L.marker([f.coordinates[1],f.coordinates[0]],{icon,interactive:false}).addTo(this.labels)}
    }
  }
  async syncDatasets(visible){const configs={road:['roads','#95a28d',1.5],mela_road:['melaRoads','#b8833b',2],pontoon_approaches:['pontoonApproaches','#b8833b',2],railway:['railways','#687c76',1],network:['network',null,2],routes:['routes','#a76c40',3],police_temporary:['temporaryPolice','#5873a3',2]};
    for(const [toggle,[key,color,weight]] of Object.entries(configs)){
      const enabled=visible.has(toggle==='pontoon_approaches'?'mela_road':toggle);if(!enabled){this.layers[toggle]?.remove();continue}if(this.layers[toggle]){if(!this.map.hasLayer(this.layers[toggle]))this.layers[toggle].addTo(this.map);continue}if(this.loading?.has(toggle))continue;(this.loading??=new Set()).add(toggle);
      try{const d=this.datasets[key]||await this.fetchJSON(this.atlas.datasets[key]);this.datasets[key]=d;
        const l=L.geoJSON(d,{renderer:this.renderer,filter:f=>!this.lowOnly||f.properties.confidence==='low',style:f=>({color:color||{osm_road:'#718f80',mela_road:'#c49c4b',pontoon:'#6a78ad',access:'#b9695a'}[f.properties.kind]||'#81937c',weight:toggle==='network'&&f.properties.kind==='access'?1.5:weight,opacity:.8}),onEachFeature:(f,l)=>{const p=f.properties;l.bindTooltip(`${esc(p.name||p.id||key)}<br>Source: ${esc(p.source||'osm')} · ${esc(p.confidence||'unknown')}${p.length_m?'<br>'+Math.round(p.length_m)+' m':''}${p.approx_width_m?'<br>Width ~'+p.approx_width_m+' m ('+esc((p.width_source||'').replace(/_/g,' '))+')':''}`,{sticky:true})}});this.layers[toggle]=l;if(this.last?.visible.has(toggle==='pontoon_approaches'?'mela_road':toggle))l.addTo(this.map);
      }catch(e){console.warn(`Map layer ${key}:`,e.message);toast(`Could not load ${key}; retry the layer toggle.`)}finally{this.loading.delete(toggle)}
    }
  }
  setLowOnly(value){this.lowOnly=value;Object.values(this.layers).forEach(l=>l.remove());this.layers={};if(this.last)this.render(this.last.features,this.last.visible,this.last.selected,this.last.operations)}
}
