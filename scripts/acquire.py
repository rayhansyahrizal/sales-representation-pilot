#!/usr/bin/env python3
"""Acquire declared sources without bypassing access controls and record checksums."""
import hashlib, json, pathlib, shutil, urllib.request, zipfile
ROOT = pathlib.Path(__file__).resolve().parents[1]

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()

def fetch(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        with urllib.request.urlopen(url) as r, dest.open('wb') as f: shutil.copyfileobj(r,f)

def main():
    spec=json.loads((ROOT/'manifests/sources.json').read_text())['datasets']
    archives={
      'online_retail_ii': ROOT/'data/raw/online_retail_ii/online_retail_ii.zip',
      'retailrocket': ROOT/'data/raw/retailrocket/retailrocket.zip'}
    # Preserve a previously downloaded temporary archive from the documented endpoint.
    tmp=pathlib.Path('/tmp/retailrocket.zip')
    if tmp.exists() and not archives['retailrocket'].exists(): shutil.move(tmp, archives['retailrocket'])
    records={}
    for name, archive in archives.items():
        fetch(spec[name]['download_url'], archive)
        out=archive.parent
        with zipfile.ZipFile(archive) as z: z.extractall(out)
        files=[]
        for p in sorted(out.iterdir()):
            if p.is_file(): files.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha256(p)})
        records[name]={'source_url':spec[name]['download_url'],'files':files}
    (ROOT/'manifests/acquisition.json').write_text(json.dumps(records,indent=2,sort_keys=True)+'\n')
if __name__=='__main__': main()
