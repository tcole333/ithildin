"""Independent local verification of preserved audio comparisons; no network."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
RATE = 16000


def decode(file_path):
    raw = subprocess.check_output(
        [
            "ffmpeg", "-nostdin", "-v", "error", "-i", str(file_path),
            "-map", "0:a:0", "-ac", "1", "-ar", str(RATE),
            "-c:a", "pcm_f32le", "-f", "f32le", "-",
        ]
    )
    values = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    return raw, values


def all_overlap_pearsons(a, b, max_lag):
    """Convolve with reversed B, then center each overlapping pair separately."""
    size = len(a) + len(b) - 1
    fft_size = 1 << (size - 1).bit_length()
    products = np.fft.irfft(
        np.fft.rfft(a, fft_size) * np.fft.rfft(b[::-1], fft_size),
        fft_size,
    )[:size]
    lags = np.arange(-min(len(b) - 1, max_lag), min(len(a) - 1, max_lag) + 1)
    start_a = np.maximum(lags, 0)
    start_b = np.maximum(-lags, 0)
    counts = np.minimum(len(a) - start_a, len(b) - start_b)
    keep = counts >= 3
    lags, start_a, start_b, counts = (
        values[keep] for values in (lags, start_a, start_b, counts)
    )

    def overlap_sums(values, starts):
        sums = np.concatenate(([0.0], np.cumsum(values)))
        squares = np.concatenate(([0.0], np.cumsum(values * values)))
        return (
            sums[starts + counts] - sums[starts],
            squares[starts + counts] - squares[starts],
        )

    sum_a, square_a = overlap_sums(a, start_a)
    sum_b, square_b = overlap_sums(b, start_b)
    numerator = products[lags + len(b) - 1] - sum_a * sum_b / counts
    denominator = np.sqrt(
        np.maximum(square_a - sum_a * sum_a / counts, 0.0)
        * np.maximum(square_b - sum_b * sum_b / counts, 0.0)
    )
    scores = np.divide(
        numerator, denominator,
        out=np.full_like(numerator, np.nan), where=denominator > 1e-20,
    )
    return lags, scores, counts


def aligned_at(a, b, lag):
    aa, bb = a[max(lag, 0):], b[max(-lag, 0):]
    count = min(len(aa), len(bb))
    return aa[:count], bb[:count]


def compare(a, b, rate):
    lags, scores, counts = all_overlap_pearsons(a, b, 10 * rate)
    best = int(np.nanargmax(np.abs(scores)))
    lag = int(lags[best])
    aa, bb = aligned_at(a, b, lag)
    return {
        "best_lag_samples": lag,
        "best_lag_seconds": lag / rate,
        "overlap_samples": int(counts[best]),
        "overlap_seconds": int(counts[best]) / rate,
        "exact_overlap_centered_pearson": float(np.corrcoef(aa, bb)[0, 1]),
        "fft_score": float(scores[best]),
    }


def envelope(values):
    complete = len(values) // 160
    blocks = values[:complete * 160].reshape(complete, 160)
    return np.sqrt(np.mean(blocks * blocks, axis=1))


def brute_force_test():
    rng = np.random.default_rng(21847)
    largest_error = 0.0
    checked = 0
    for size_a, size_b in [(11, 8), (8, 11), (13, 13)]:
        a, b = rng.normal(size=size_a), rng.normal(size=size_b)
        lags, scores, _ = all_overlap_pearsons(a, b, 5)
        for lag, score in zip(lags, scores, strict=True):
            aa, bb = aligned_at(a, b, int(lag))
            error = abs(float(score) - float(np.corrcoef(aa, bb)[0, 1]))
            largest_error = max(largest_error, error)
            checked += 1
    assert largest_error < 1e-12
    return {"lag_pairs_checked": checked, "max_absolute_error": largest_error}


def apsnr_counterexample():
    command = [
        "ffmpeg", "-hide_banner", "-nostats", "-nostdin",
        "-i", "/tmp/osint-E6iGgeNz/cloud-instagram-Dcg3GEFhIaG-video.mp4",
        "-i", str(ROOT / "d-control-997hz.wav"),
        "-filter_complex",
        "[0:a]asetpts=PTS-STARTPTS,atrim=duration=51[a0];"
        "[1:a]asetpts=PTS-STARTPTS,atrim=duration=51[a1];[a0][a1]apsnr",
        "-vn", "-f", "null", "-",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    completed.check_returncode()
    log_path = ROOT / "h-apsnr-known-different-control.log"
    log_path.write_text(completed.stderr)
    return {
        "command": command,
        "log_file": str(log_path),
        "channels_db": {
            channel: float(value)
            for channel, value in re.findall(r"PSNR ch(\d+): ([0-9.]+) dB", completed.stderr)
        },
    }


def main():
    previous = json.loads((ROOT / "d-audio-comparison.json").read_text())
    raw_data, decoded, metadata = {}, {}, {}
    for name, data in previous["files"].items():
        file_path = Path(data["source_file"])
        raw, values = decode(file_path)
        raw_data[name], decoded[name] = raw, values
        digest = hashlib.sha256(raw).hexdigest()
        metadata[name] = {
            "source_file": str(file_path),
            "source_sha256": hashlib.sha256(file_path.read_bytes()).hexdigest(),
            "decoded_pcm_sha256": digest,
            "decoded_samples": len(values),
            "hash_matches_D": digest == data["decoded_pcm_sha256"],
            "sample_count_matches_D": len(values) == data["decoded_samples"],
        }

    base = decoded["baseline_politicalhub"]
    decoded["control_same_source_shifted_one_second"] = base[RATE:]
    decoded["control_known_different_997hz_sine"] = (
        0.1 * np.sin(2 * np.pi * 997 * np.arange(len(base)) / RATE)
    )
    comparisons = {}
    for name, values in decoded.items():
        if name == "baseline_politicalhub":
            continue
        comparisons[name] = {
            "waveform": compare(base, values, RATE),
            "rms_envelope_10ms": compare(envelope(base), envelope(values), 100),
        }
        declared = previous["comparisons"][name]["waveform"]
        aa, bb = aligned_at(base, values, declared["best_lag_samples"])
        measured = float(np.corrcoef(aa, bb)[0, 1])
        comparisons[name]["D_reported_lag_direct_check"] = {
            "pearson": measured,
            "absolute_difference_from_D": abs(measured - declared["aligned_pearson"]),
        }

    _, actual_sine = decode(ROOT / "d-control-997hz.wav")
    frequencies = np.fft.rfftfreq(len(actual_sine), 1 / RATE)
    power = np.abs(np.fft.rfft(actual_sine))
    result = {
        "method": "Fresh FFmpeg mono 16000-Hz float32-LE decoding; independent reverse-convolution FFT with exact per-overlap centering; maximum absolute Pearson within +/-10 seconds.",
        "ffmpeg_version": subprocess.check_output(
            ["ffmpeg", "-version"], text=True, stderr=subprocess.DEVNULL,
        ).splitlines()[0],
        "brute_force_unit_check": brute_force_test(),
        "files": metadata,
        "lonealpha_and_Dcg245KTBBp_pcm_bytes_identical": (
            raw_data["baseline_lonealpha"] == raw_data["Dcg245KTBBp"]
        ),
        "comparisons": comparisons,
        "preserved_997hz_control_wav": {
            "dominant_frequency_hz": float(frequencies[int(np.argmax(power))]),
            "decoded_samples": len(actual_sine),
            "waveform_vs_baseline": compare(base, actual_sine, RATE),
        },
        "apsnr_known_different_reproduction": apsnr_counterexample(),
        "limitations": [
            "Mono resampling can erase channel-specific and high-frequency differences; equal decoded PCM is equality under this specified transform, not proof of identical original source files.",
            "A high waveform correlation supports shared sound content over the measured overlap, not common ownership, funder, or synchronized posting.",
            "This verifies preserved local inputs and computation; it is not an authentication of how source media were acquired.",
        ],
    }
    (ROOT / "h-audio-qa-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
