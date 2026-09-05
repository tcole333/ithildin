# Track D preservation and comparison methods

Access was passive and unauthenticated. Exact public Instagram reel URLs and their `/reel/SHORTCODE/embed/` counterparts were fetched with `curl -L --max-time 45 -sS --fail`; response headers were preserved temporarily. The embed's JSON-escaped `contextJSON` supplied `gql_data.shortcode_media`, captions, owner/media IDs, durations, counts, and a public media URL. Only the exact disclosed URL was fetched. Raw HTML/headers can contain signed URLs or cookies and are excluded from durable artifacts. Sanitized JSON retains hashes, response Date, source URLs and field names. Response Date is server-provided capture context, not a post timestamp.

## Tools and exact transforms

- FFmpeg 8.0.1, Homebrew `8.0.1_2`, Apple clang 17.0.0; libavutil 60.8.100, libavcodec 62.11.100, libavformat 62.3.100, libavfilter 11.4.100, libswresample 6.1.100.
- MP4 hashes: SHA-256 over exact downloaded bytes.
- Caption hashes: SHA-256 of the UTF-8 string parsed from `edge_media_to_caption.edges[].node.text`, joining multiple edges with a newline. No stripping, lowercase conversion or punctuation normalization.
- PCM hashes: `ffmpeg -v error -i FILE -ac 1 -ar 16000 -f f32le -`. The hash is of decoded mono 16 kHz float32-LE bytes. This does not establish equality of original stereo channels, frequencies above the retained bandwidth, or encoded video files.
- Main visual comparison:
  `ffmpeg -hide_banner -nostats -i BASE -i CANDIDATE -filter_complex '[0:v]setpts=PTS-STARTPTS,format=yuv420p[v0];[1:v]setpts=PTS-STARTPTS,format=yuv420p[v1];[v0][v1]ssim=shortest=1:stats_file=FRAMELOG' -an -f null -`
- Extension visual comparison additionally normalizes both full frames using `scale=360:640,setsar=1,fps=25` before SSIM. Exact commands are in `d-extension-comparison.json`. This was required by unequal dimensions/frame rates. Global SSIM is affected by black/white borders, logos, spatial position and cadence; it is never used alone as a match criterion.
- Contact sheets: primary set `fps=1/20,scale=360:640,tile=3x1`; extension set `fps=1/10,scale=270:480,tile=3x1`, one sheet each. They are sampled frames, not a claim to full manual playback.

## Rejected APSNR statistic

The original pipeline was:

```text
ffmpeg -hide_banner -nostats -i BASE -i CANDIDATE -filter_complex '[0:a]asetpts=PTS-STARTPTS,atrim=duration=51[a0];[1:a]asetpts=PTS-STARTPTS,atrim=duration=51[a1];[a0][a1]apsnr' -vn -f null -
```

A control was generated with:

```text
ffmpeg -f lavfi -i 'sine=frequency=997:sample_rate=44100:duration=51' -ac 2 -c:a pcm_f32le d-control-997hz.wav
```

The unrelated sine versus the baseline speech returned 173.52 dB, similar to the roughly 174 dB returned for related and unrelated speech. That magnitude is therefore excluded as identity evidence in this investigation. This is a counterexample to this pipeline, not a diagnosis of FFmpeg's general implementation. Root corrected finding15323 and the old launch brief after independent QA.

## Validated audio comparison

`d-audio-compare.py` uses FFT normalized cross-correlation over ±10 seconds after subtracting each full signal's mean, then reports true Pearson/RMSE for the selected overlap. Its search score is not generally exact overlap-centered Pearson. The independent `h-audio-qa.py` reimplemented exact separately centered Pearson for every overlap, verified the calculation against brute force, and selected the same lags/results for these inputs. See root-owned `report-audio-qa.md` and `h-audio-qa-results.json`.

Positive lag removes samples from the beginning of the baseline. The politicalhub/lonealpha pair aligns at +766 samples (47.875 ms), overlapping 51.0156875 seconds, Pearson 0.9458160882. Separate 10-ms RMS envelopes correlate 0.9846651297 at +50 ms. A one-second shifted copy recovers +1 second with correlation 1; a known-different sine is about0.00382. Do not confuse audio alignment with post-ID timing or interpret correlation as attribution probability.

## Timestamp derivation

The historical primary scheme in Mike Krieger's April2012 `Sharding @ Instagram` presentation uses41 time bits,13 shard bits and10 sequence bits, with epoch1314220021721 milliseconds. Applied formula: `(int(media_id) >> 23) + 1314220021721`.

Source: https://media.postgresql.org/sfpug/instagram_sfpug.pdf (slides131-136; code on135). These are **MEDIA-ID-DERIVED generation times**, not independently observed publication timestamps. The embeds omit `taken_at_timestamp`; the historic scheme's invariance in2026 is not independently guaranteed. Exact derived gaps are conditional measurements, not proof of scheduler synchronization.

## Durable media mapping

All eleven analyzed Instagram MP4s are in `media/`. Nine new files use `d-instagram-SHORTCODE.mp4`; two baseline files retain `cloud-instagram-SHORTCODE-video.mp4`. Original temporary-path references in analysis scripts/logs resolve by basename to this media directory. The complete main and extension sanitized metadata JSON files hold acquisition hashes and source URLs. No signed media URL is needed to reproduce a local comparison.
