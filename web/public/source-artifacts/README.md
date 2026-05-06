# Source Artifacts

This directory contains source files that the platform can serve directly from
source record pages. Add a `hosted_asset_url` in `web/src/data/source-records.json`
that points at the public path, for example:

```json
{
  "Example-Source-p4": {
    "kind": "hosted_copy",
    "hosted_asset_url": "/source-artifacts/example-source.pdf#page=4"
  }
}
```

Use hosted artifacts for public records that were downloaded manually or that
need a durable local copy. Do not place restricted, private, or non-redistributable
documents here.
