#!/usr/bin/env python3
"""Local preview. Serve the optional newspaper reference only from its private path."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
ROOT=Path(__file__).resolve().parents[1]
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)
 def translate_path(self,path):
  if path.split('?')[0]=='/__local_reference__/source-map.jpg':return str(ROOT/'local-reference/source-map.jpg')
  return super().translate_path(path)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);a=p.parse_args()
 print(f'Local: http://127.0.0.1:{a.port}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
