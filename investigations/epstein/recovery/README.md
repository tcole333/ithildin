# Epstein public-file recovery queue

This directory tracks recovery status for corrupted or OCR-damaged artifacts
from the public DOJ Epstein Library. It is an infrastructure ledger, not a
finding store and not evidence that the underlying document contents are true.

The queue follows three rules:

1. Do not redo a recovery when a usable public artifact or reproducible method
   already exists.
2. Do not call generated or inferred bytes a recovery. An output byte must
   trace to source bytes, source pixels, or a documented OCR consensus; any
   unresolved glyph stays ambiguous.
3. Preserve the original URL, capture timestamp, length, and hashes before
   transformation. Unknown media remains quarantined and metadata-only until it
   is classified.

Use the ledger and local harness:

```bash
WORKDIR=$(mktemp -d /tmp/osint-XXXXXXXX)

uv run python tools/epstein_recovery.py ledger --actionable \
  --output "$WORKDIR/actionable.json"

uv run python tools/epstein_recovery.py inspect "$WORKDIR/EFTA00147557.pdf" \
  --efta-id EFTA00147557 \
  --expected-sha256 88f9a0740d4a8b04b966fa8ce7d423bbc4e3bd495a60f7cbc89df14b8cc7ee64 \
  --output "$WORKDIR/inspect.json"
```

`decode-infopath` fails closed: it writes nothing unless strict Base64 decoding,
the InfoPath signature and fixed header, the UTF-16LE filename, and the declared
body length all agree. This format contract comes from Microsoft's published
InfoPath attachment encoder/decoder example:

<https://learn.microsoft.com/en-us/previous-versions/office/troubleshoot/office-developer/encode-and-decode-attachment-using-visual-c-in-infopath-2010>

Recovered derivatives belong outside the source tree (for example,
`output/epstein-recovery/EFTA.../`) with a provenance JSON alongside each
artifact. Do not replace or edit the original.
