# Provider documentation checked before service request

Reviewed 2026-09-02, immediately before the 18:49:03 UTC request. These are analyst summaries of successfully retrieved official provider pages, not raw HTTP captures.

- [Buckets: get](https://docs.cloud.google.com/storage/docs/json_api/v1/buckets/get), lines 131–166 in web capture: GET on `/storage/v1/b/{bucket}` returns bucket metadata; documented permission is `storage.buckets.get`. No request body. `projection=noAcl` omits owner and ACL properties. The selected fields further limit a successful response. More sensitive policy metadata has additional permissions, and was not requested.
- [Common parameters](https://docs.cloud.google.com/storage/docs/json_api/v1/parameters), lines 414–433: `fields` selects a response subset.
- [JSON API overview](https://docs.cloud.google.com/storage/docs/json_api), lines 139–169: partial responses can request comma-separated fields, with field names relative to the returned bucket resource. Successful valid requests return the selected data; invalid selections receive 400.

The cloud.google.com common-parameters URL timed out once in the web reader; following the official link to docs.cloud.google.com succeeded. No service request was made during documentation review.
