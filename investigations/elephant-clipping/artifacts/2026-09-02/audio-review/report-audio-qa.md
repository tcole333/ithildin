---
status: completed
profile: elephant-clipping
task: independent-local-audio-qa
collector: agent:manual-baseline-hygiene
completed_utc: 2026-09-02
findings_edited: []
connections_edited: []
result: replacement_metrics_reproduced_apsnr_counterexample_confirmed
---

# Independent audio QA

## Conclusion

The replacement audio evidence is reproducible on the preserved local inputs.
Fresh decoding confirms all five reported PCM hashes and sample counts. The
`Dcg245KTBBp` file attributed by Track D to `theusdebatearena` and the baseline
`Dcg3HQQTea6` file attributed to `lonealphapolitics` decode to **byte-identical
mono 16 kHz float32-LE PCM**, containing 816,251 samples.

An independently implemented, exact per-overlap-centered Pearson search
reproduces the baseline-pair alignment and scores: trim 766 samples
(47.875 milliseconds) from the beginning of `_politicalhub`'s decoded audio,
then compare 51.0156875 seconds of overlap. Waveform Pearson is
`0.9458160882200786`; the separate 10-millisecond RMS-envelope comparison gives
`0.9846651297187634` at a 50-millisecond alignment.

The original approximately 174 dB APSNR magnitude must not be used as audio
identity evidence in this investigation. I independently reran Track D's exact
known-different filter pipeline, adding only `-nostdin`: a preserved 997 Hz sine
wave versus the baseline speech again returned **173.52 dB on both channels**
under FFmpeg 8.0.1. This validates the counterexample, not a diagnosis of the
filter implementation's root cause.

No finding, connection, launch brief, root plan, or Track D artifact was edited
during this audio QA. Root retains responsibility for the reviewed correction
to finding 15323's audio claim and related prose.

## Independent method

I read all of `d-audio-compare.py` and `d-audio-comparison.json`, inspected the
preserved APSNR logs, and obtained the exact known-different command from Track
D. I did not execute Track D's script because it writes its own result file.

The separate `h-audio-qa.py`:

1. Decodes each original local media file afresh using FFmpeg, explicitly
   selecting its first audio stream and outputting mono 16,000 Hz float32-LE PCM.
2. Computes SHA-256 over those actual decoded bytes and compares counts/hashes
   against Track D's record.
3. Computes the cross-products by FFT convolution with the reversed candidate,
   then calculates exact separately centered Pearson correlation for each
   overlapping interval within ±10 seconds.
4. Selects the largest absolute correlation while retaining its sign, and
   independently checks the reported result with direct `numpy.corrcoef` at the
   selected overlap.
5. Repeats the comparison on 10-millisecond RMS envelopes and on positive and
   negative controls.
6. Reruns the exact known-different APSNR pipeline and preserves its new stderr
   log separately.

The independent FFT/cumulative-sum implementation was checked against direct
brute-force Pearson calculations for 33 small unequal/equal-length lag pairs;
maximum absolute error was `7.216449660063518e-16`. `ruff check` passes for the
QA script. Local versions were NumPy 2.4.3 and FFmpeg 8.0.1.

## Reproduced comparisons

Positive lag means removing that duration from the beginning of the baseline
before comparing the overlap. Scores below are signed correlations, not
probabilities or attribution confidence.

| Baseline compared with | Best waveform lag | Overlap | Waveform Pearson | RMS-envelope Pearson |
|---|---:|---:|---:|---:|
| `baseline_lonealpha` / `Dcg3HQQTea6` | +0.047875 s | 51.0156875 s | 0.9458160882 | 0.9846651297 |
| `Dcg245KTBBp` | +0.047875 s | 51.0156875 s | 0.9458160882 | 0.9846651297 |
| `Dchbt_aS0dF` | −8.59275 s | 51.155 s | 0.0143419302 | −0.1334790628 |
| `DcfbnTrMnBs` | −8.25475 s | 43.178875 s | −0.0117713626 | −0.1029908690 |
| Same baseline with first second removed | +1.000000 s | 50.155 s | 1.0000000000 | 1.0000000000 |
| Synthetic known-different 997 Hz sine | +9.9319375 s | 41.2230625 s | 0.0038214743 | −0.0552779451 |

The envelope correlations have their own independently selected lag and
overlap; the table's lag/overlap columns refer to the waveform comparison.
Detailed envelope values are preserved in `h-audio-qa-results.json`.

I also decoded the actual `d-control-997hz.wav` used in the APSNR experiment,
verified a dominant frequency of exactly 997 Hz, and obtained waveform Pearson
`0.0038217639309463232` against the baseline at the best allowed lag. Thus the
preserved control file itself, not only an in-memory synthetic reconstruction,
is a valid known-different sound for this test.

## Actual decoded hashes

Every hash/count matched Track D's earlier JSON on fresh decoding.

| Local media | Decoded samples | SHA-256 of mono 16 kHz float32-LE bytes |
|---|---:|---|
| `Dcg3GEFhIaG` (`baseline_politicalhub`) | 818,480 | `6011c347e550613bf2a9b5fdbb0635f17c756c5ca325e2bbd810efe643d198a5` |
| `Dcg3HQQTea6` (`baseline_lonealpha`) | 816,251 | `6904c56827ca1d0252afedef6eb729bfa8dbf2f3b755406b3ab59416fb8a16f6` |
| `Dcg245KTBBp` | 816,251 | `6904c56827ca1d0252afedef6eb729bfa8dbf2f3b755406b3ab59416fb8a16f6` |
| `Dchbt_aS0dF` | 981,205 | `86e042c4d7fb0614bbab1b3b2f57f5d34ca15fea09444bf12234bbe7aa6f49e7` |
| `DcfbnTrMnBs` | 822,938 | `c3d5cd12878ea580eb44c34a92020068a39c38fe65d1a8048fcd5aa448c241b5` |

I additionally compared the decoded byte strings directly; the lonealpha and
`Dcg245KTBBp` byte strings are equal. Their original downloaded MP4 hashes are
different, so this is not a claim that the MP4 files themselves are identical.

## Script-review observations and limits

- Track D's lag-search score is normalized cross-correlation after subtracting
  each whole signal's mean. It is not, in general, exact separately centered
  Pearson for every possible overlap. Track D does calculate true Pearson for
  its selected overlap. My independent exact per-overlap-centered search chose
  the same lags for every tested waveform and envelope, so this distinction did
  not change the reported results for these inputs.
- Absolute-correlation maximization can select inverted audio or negative
  envelope matches. Retaining the sign, the overlap, and the negative controls
  is important; the small negative scores above do not establish a match.
- Mono downmixing and resampling are a specified transform. Equal bytes after
  that transform do not establish equality of original channels, frequencies
  above the retained bandwidth, encoded files, or complete video content.
- A high waveform correlation over the stated overlap supports shared sound
  content. It does not prove common account ownership, campaign enrollment,
  funding, or posting synchronization. The 47.875-millisecond audio offset is a
  media-alignment measurement, not the media-ID-derived posting interval.
- This task verifies preserved local inputs and computation. It does not
  independently authenticate account attribution or the acquisition chain; that
  remains Track D's source-provenance responsibility.
- The APSNR counterexample disqualifies the observed magnitude as a reliable
  identity discriminator in this pipeline. Do not generalize from this bounded
  test to every possible PSNR implementation or infer the software root cause.

## Preserved QA artifacts

- [Independent QA script](/tmp/osint-ldT6picn/h-audio-qa.py)
- [Independent full results](/tmp/osint-ldT6picn/h-audio-qa-results.json)
- [Independent APSNR counterexample log](/tmp/osint-ldT6picn/h-apsnr-known-different-control.log)
- [Reviewed Track D script](/tmp/osint-ldT6picn/d-audio-compare.py)
- [Reviewed Track D results](/tmp/osint-ldT6picn/d-audio-comparison.json)

The full results include exact input paths, original MP4 hashes, decoded hashes,
lag/sample counts, controls, method details, and the reproduced FFmpeg command.

## Learnings

- An impressive similarity number is not evidence until a known-different
  control demonstrates that the measurement discriminates between inputs.
- Validate both alignment direction and correlation with a known shifted copy;
  zero-lag correlation can be near zero even for closely related encoded audio.
- Independently recompute selected lags with overlap-specific centering rather
  than trusting a similarly named metric or copied implementation.
- State exactly which transformation a hash covers. Decoded mono-PCM equality
  is a strong, narrow result; it is not complete source-file identity.
- Keep media alignment, platform timestamp derivation, content similarity, and
  actor attribution separate in summaries and evidence assessments.
