#!/usr/bin/env python3
"""Landmarks missing from OSM and Wikidata, located on Google Maps (looked up 26 October 2026).
Coordinates come from the place pin, or from the plus code shown in the result list.
Lankeshwar is not on Google Maps; Gangeshwar has several same-name temples, none at the
TOI position (east bank, south of Shankh Madhav), so both stay unresolved.
"""
import json,pathlib
from openlocationcode import openlocationcode as olc
R=pathlib.Path(__file__).resolve().parents[1]
REF=(25.43,81.88)
# id, name, google place name, (lat, lon) from the pin or a plus code
PLACES=[
 ('landmark-beni','Shri Beni Madhav','Shri Veni Madhav Mandir, Daraganj',(25.445775,81.8833726)),
 ('landmark-samudra','Samudra Koop','Samudra Koop, Jhusi',(25.4256279,81.900071)),
 ('landmark-aadi','Aadi Veni Mahadev','Shri Adi Veni Madhav Temple (Dwadash Madhav), Arail',(25.4199448,81.881436)),
 ('landmark-chakra','Chakra Madhav','Shri Chakra Madhav Mandir (Dwadash Madhav), Arail','CV6Q+972'),
 ('landmark-shankh','Shankh Madhav','Shri Shankh Madhav Mandir, Chhatnag Road, Jhusi','CW45+R5W'),
 ('landmark-someshwar','Someshwar Mahadev','Shri Someshwar Mahadev Mandir, Arail Ghat','CV4R+R9V'),
]
def latlon(loc):
 if isinstance(loc,tuple):return loc
 a=olc.decode(olc.recoverNearest(loc,*REF));return (a.latitudeCenter,a.longitudeCenter)
fs=[]
for ident,name,google_name,loc in PLACES:
 lat,lon=latlon(loc)
 props={'id':ident,'name':name,'type':'landmark','source':'google_maps','confidence':'medium','google_name':google_name,'plus_code':loc if isinstance(loc,str) else None,'looked_up':'2026-10-26','note':'Position from Google Maps; not in OSM or Wikidata.'}
 fs.append({'type':'Feature','id':ident,'properties':props,'geometry':{'type':'Point','coordinates':[lon,lat]}})
(R/'data/mela/landmarks_google.geojson').write_text(json.dumps({'type':'FeatureCollection','name':'landmarks_google','features':fs},ensure_ascii=False,indent=2))
print(f'{len(fs)} Google Maps landmarks; Lankeshwar and Gangeshwar unresolved')
