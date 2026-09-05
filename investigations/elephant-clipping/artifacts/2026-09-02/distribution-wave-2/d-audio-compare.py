import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
SAMPLE_RATE = 16000
FILES = {
    "baseline_politicalhub": "/tmp/osint-E6iGgeNz/cloud-instagram-Dcg3GEFhIaG-video.mp4",
    "baseline_lonealpha": "/tmp/osint-E6iGgeNz/cloud-instagram-Dcg3HQQTea6-video.mp4",
    "Dcg245KTBBp": str(ROOT / "d-instagram-Dcg245KTBBp.mp4"),
    "Dchbt_aS0dF": str(ROOT / "d-instagram-Dchbt_aS0dF.mp4"),
    "DcfbnTrMnBs": str(ROOT / "d-instagram-DcfbnTrMnBs.mp4"),
}


def decode(path):
    data = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "-"])
    return np.frombuffer(data, dtype="<f4").astype(np.float64), hashlib.sha256(data).hexdigest()


def compare(a, b, rate, max_lag_seconds=10):
    a = a - np.mean(a)
    b = b - np.mean(b)
    nfft = 1 << (len(a) + len(b) - 2).bit_length()
    cross = np.fft.irfft(np.fft.rfft(a, nfft) * np.conj(np.fft.rfft(b, nfft)), nfft)
    full = np.concatenate((cross[-(len(b)-1):], cross[:len(a)]))
    lags = np.arange(-min(len(b)-1, int(max_lag_seconds*rate)), min(len(a)-1, int(max_lag_seconds*rate))+1)
    astart = np.maximum(lags, 0)
    bstart = np.maximum(-lags, 0)
    count = np.minimum(len(a)-astart, len(b)-bstart)
    ac = np.concatenate(([0.0], np.cumsum(a*a)))
    bc = np.concatenate(([0.0], np.cumsum(b*b)))
    denom = np.sqrt((ac[astart+count]-ac[astart])*(bc[bstart+count]-bc[bstart]))
    scores = full[lags+len(b)-1]/np.maximum(denom, 1e-30)
    best = int(np.argmax(np.abs(scores)))
    lag = int(lags[best])
    n = int(count[best])
    aa = a[int(astart[best]):int(astart[best])+n]
    bb = b[int(bstart[best]):int(bstart[best])+n]
    gain = float(np.dot(aa, bb)/np.dot(bb, bb))
    residual = aa-gain*bb
    n0 = min(len(a),len(b))
    return {
        "zero_lag_pearson": float(np.corrcoef(a[:n0],b[:n0])[0,1]),
        "best_lag_samples": lag,
        "best_lag_seconds": lag/rate,
        "lag_definition": "positive means remove this many samples from the start of baseline before comparison",
        "aligned_overlap_seconds": n/rate,
        "aligned_pearson": float(np.corrcoef(aa,bb)[0,1]),
        "aligned_rmse": float(np.sqrt(np.mean((aa-bb)**2))),
        "gain_fitted_to_candidate": gain,
        "gain_fitted_residual_rms_div_baseline_rms": float(np.sqrt(np.mean(residual**2)/np.mean(aa**2))),
    }


def envelope(a):
    width = 160
    n = len(a)//width
    return np.sqrt(np.mean(a[:n*width].reshape(n,width)**2, axis=1))


decoded = {}
metadata = {}
for name, path in FILES.items():
    decoded[name], digest = decode(path)
    metadata[name] = {"source_file": path, "decoded_pcm_sha256": digest, "decoded_samples": len(decoded[name]), "duration_seconds": len(decoded[name])/SAMPLE_RATE}
base = decoded["baseline_politicalhub"]
decoded["control_same_source_shifted_one_second"] = base[SAMPLE_RATE:]
decoded["control_known_different_997hz_sine"] = 0.1*np.sin(2*np.pi*997*np.arange(len(base))/SAMPLE_RATE)
results = {}
for name, values in decoded.items():
    if name == "baseline_politicalhub":
        continue
    results[name] = {
        "waveform": compare(base, values, SAMPLE_RATE),
        "rms_envelope_10ms": compare(envelope(base), envelope(values), 100),
    }
result = {
    "method": "ffmpeg decoded mono 16000 Hz float32 LE PCM; numpy float64 FFT normalized cross-correlation over +/-10 seconds; exact overlap and gain-fitted RMSE; separate 10ms RMS envelope comparison",
    "files": metadata,
    "comparisons": results,
    "limitations": "Codec/resampling, time stretching, music, edits, and local lag can reduce waveform similarity. Whole-clip alignment does not establish that all segments share an original. Synthetic control is a diagnostic only.",
}
(ROOT/"d-audio-comparison.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(results, indent=2))
