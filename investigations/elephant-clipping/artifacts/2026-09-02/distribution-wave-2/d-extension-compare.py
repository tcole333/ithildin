import hashlib
import json
import re
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
metadata = {r['shortcode']: r for r in json.loads((root/'d-extension-post-metadata.json').read_text())}
pairs = [
    ('Dcyh2RcyfT8', 'DcyUDEkyN_1'),
    ('Dcx9xisylQp', 'Dcx0jZ1SnC8'),
    ('Dcics_thlwQ', 'DcvOLk7xFni'),
]
results = []
for a, b in pairs:
    files = [root/f'd-instagram-{s}.mp4' for s in (a,b)]
    pcm = [subprocess.check_output(['ffmpeg','-v','error','-i',str(f),'-ac','1','-ar','16000','-f','f32le','-']) for f in files]
    stats = root/f'd-ssim-{a}-{b}-frames.log'
    invocation = ['ffmpeg','-hide_banner','-nostats','-i',str(files[0]),'-i',str(files[1]),'-filter_complex',f'[0:v]setpts=PTS-STARTPTS,scale=360:640,setsar=1,fps=25,format=yuv420p[v0];[1:v]setpts=PTS-STARTPTS,scale=360:640,setsar=1,fps=25,format=yuv420p[v1];[v0][v1]ssim=shortest=1:stats_file={stats}','-an','-f','null','-']
    result = subprocess.run(invocation, capture_output=True, text=True, check=True)
    (root/f'd-ssim-{a}-{b}.log').write_text(result.stderr)
    ssim = float(re.findall(r'All:([0-9.]+)',result.stderr)[-1])
    record = {
        'pair': [a,b],
        'owner_handles': [metadata[s]['owner_username'] for s in (a,b)],
        'caption_hash_equal': metadata[a]['caption_sha256_utf8']==metadata[b]['caption_sha256_utf8'],
        'caption_length_characters': metadata[a]['caption_length_characters'],
        'caption_sha256': metadata[a]['caption_sha256_utf8'],
        'media_id_derived_a_minus_b_seconds': ((int(metadata[a]['media_id'])>>23)-(int(metadata[b]['media_id'])>>23))/1000,
        'timing_caveat': 'Historical media-ID generation derivation, not explicit publication timestamp',
        'full_frame_ssim_zero_pts': ssim,
        'visual_normalization': 'Both full frames normalized to360x640, SAR1,25fps; zeroPTS alignment; no spatial crop or lag search',
        'ssim_invocation': invocation,
        'pcm_decode_invocation_template': 'ffmpeg -v error -i FILE -ac 1 -ar 16000 -f f32le -',
        'decoded_pcm_sha256': [hashlib.sha256(p).hexdigest() for p in pcm],
        'decoded_pcm_samples': [len(p)//4 for p in pcm],
        'decoded_pcm_identical': pcm[0]==pcm[1],
        'limits': 'Global SSIM can reflect shared borders/layout; inspect frames. Different PCM is not proof of a different source without alignment. No ownership or funder attribution.'
    }
    results.append(record)
(root/'d-extension-comparison.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
