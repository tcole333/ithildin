import hashlib
import json
from pathlib import Path

artifact = Path('investigations/elephant-clipping/artifacts/2026-09-02/distribution-wave-2')
files = []
for file in sorted(artifact.rglob('*')):
    if not file.is_file() or file.name == 'd-manifest.json':
        continue
    files.append({'path':str(file.relative_to(artifact)), 'bytes':file.stat().st_size, 'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
posts = []
for name in ['d-public-post-metadata.json', 'd-baseline-public-post-metadata.json', 'd-extension-post-metadata.json']:
    posts.extend(json.loads((artifact/name).read_text()))
manifest = {
    'profile':'elephant-clipping', 'track':'D', 'date':'2026-09-02',
    'scope':'9 newly acquired Instagram MP4s plus2 preserved baseline MP4s; no renewed account census',
    'excluded':'Raw HTML/full headers and signed CDN URLs; incidental identifiers not relevant to attribution',
    'media_count':len(list((artifact/'media').glob('*.mp4'))),
    'posts':[{'shortcode':p['shortcode'],'source_url':p['source_url'],'owner_username':p['owner_username'],'media_id':p['media_id'],'capture_response_date_utc':p['response_date_header_utc'],'media_sha256':p['media_sha256']} for p in posts],
    'files':files,
}
(artifact/'d-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'manifest':str(artifact/'d-manifest.json'),'files':len(files),'media_count':manifest['media_count'],'bytes':sum(f['bytes'] for f in files)}))
