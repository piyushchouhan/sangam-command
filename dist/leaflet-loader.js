'use strict';
window.leafletReady=new Promise((resolve,reject)=>{function load(url,fallback){const s=document.createElement('script');s.src=url;s.onload=resolve;s.onerror=()=>fallback?load('vendor/leaflet/leaflet.js',false):reject(Error('Leaflet could not load'));document.head.appendChild(s)}load('https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js',true)});
