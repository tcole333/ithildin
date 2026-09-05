from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import pytest

from tools import query_oregon_multnomah_sail as sail
from tools.public_records_contract import ResultStatus
from tools.public_records_http import SourceSchemaError


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "public_records"
    / "oregon_multnomah_sail"
)
LIVE = os.environ.get("LIVE_PUBLIC_RECORDS") == "1"


def fixture_text(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> Any:
    return json.loads(fixture_text(name))


def args_for(*values: str) -> Any:
    return sail.build_parser().parse_args(list(values))


def component_metadata(component: sail.SAILComponent) -> dict[str, Any]:
    return {
        "id": 0,
        "name": component.layer_name,
        "serviceItemId": component.item_id,
        "objectIdField": component.object_id_field,
        "geometryType": component.geometry_type,
        "spatialReference": {"wkid": component.source_crs_wkids[0]},
        "maxRecordCount": 2_000,
        "advancedQueryCapabilities": {
            "supportsOrderBy": True,
            "supportsPagination": True,
        },
        "fields": [
            {
                "name": field,
                "type": (
                    "esriFieldTypeOID"
                    if field == component.object_id_field
                    else "esriFieldTypeString"
                ),
                "alias": field,
                "nullable": field != component.object_id_field,
            }
            for field in component.fields
        ],
    }


class FixtureLayerClient:
    def __init__(
        self,
        component: sail.SAILComponent,
        *,
        page_size: int = 1,
        missing_field: str | None = None,
    ) -> None:
        self.component = component
        self.page_size = page_size
        self.features = deepcopy(
            fixture_json("features.json")[component.source_id]
        )
        self.missing_field = missing_field
        self.where_calls: list[str] = []
        self.record_counts: list[int] = []

    def fetch_metadata(self) -> dict[str, Any]:
        metadata = component_metadata(self.component)
        if self.missing_field:
            metadata["fields"] = [
                field
                for field in metadata["fields"]
                if field["name"] != self.missing_field
            ]
        return metadata

    def _filtered(self, where: str) -> list[Mapping[str, Any]]:
        object_field = self.component.object_id_field
        exact_object = re.search(
            rf"\b{re.escape(object_field)}\s*=\s*([0-9]+)",
            where,
        )
        minimum = re.search(
            rf"\b{re.escape(object_field)}\s*>\s*([0-9]+)",
            where,
        )
        maximum = re.search(
            rf"\b{re.escape(object_field)}\s*<=\s*([0-9]+)",
            where,
        )
        exact_strings = re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s*=\s*'((?:''|[^'])*)'",
            where,
        )
        contains_strings = re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s+LIKE\s+'%((?:''|[^'])*)%'",
            where,
        )
        records: list[Mapping[str, Any]] = []
        for feature in self.features:
            attributes = feature["attributes"]
            object_id = attributes[object_field]
            if exact_object and object_id != int(exact_object.group(1)):
                continue
            if minimum and object_id <= int(minimum.group(1)):
                continue
            if maximum and object_id > int(maximum.group(1)):
                continue
            if exact_strings and not any(
                str(attributes.get(field) or "") == value.replace("''", "'")
                for field, value in exact_strings
            ):
                continue
            if contains_strings and not any(
                value.replace("''", "'").casefold()
                in str(attributes.get(field) or "").casefold()
                for field, value in contains_strings
            ):
                continue
            records.append(feature)
        return records

    def fetch_count(self, where: str) -> int:
        self.where_calls.append(where)
        return len(self._filtered(where))

    def fetch_page(
        self,
        *,
        where: str,
        record_count: int,
        return_geometry: bool,
        descending: bool = False,
    ) -> tuple[Mapping[str, Any], ...]:
        self.where_calls.append(where)
        self.record_counts.append(record_count)
        features = self._filtered(where)
        object_field = self.component.object_id_field
        features.sort(
            key=lambda value: value["attributes"][object_field],
            reverse=descending,
        )
        selected = deepcopy(features[:record_count])
        if not return_geometry:
            for feature in selected:
                feature.pop("geometry", None)
        return tuple(selected)


class FixtureClient:
    def __init__(self) -> None:
        self.layers: dict[str, FixtureLayerClient] = {}
        self.pdf = b"%PDF-1.4\nfixture\n%%EOF\n"

    def layer_client(
        self,
        component: sail.SAILComponent,
    ) -> FixtureLayerClient:
        layer = FixtureLayerClient(component)
        self.layers[component.source_id] = layer
        return layer

    def fetch_image_viewer(self, survey_id: str) -> sail.ResponseArtifact:
        html = fixture_text("image_05335.html").encode()
        return sail.ResponseArtifact(
            content=html,
            source_url=sail.image_viewer_url(survey_id),
            headers={
                "content-type": "text/html; charset=utf-8",
                "content-length": str(len(html)),
            },
            status_code=200,
        )

    def fetch_pdf(
        self,
        url: str,
        *,
        maximum_bytes: int,
    ) -> sail.ResponseArtifact:
        assert maximum_bytes >= len(self.pdf)
        return sail.ResponseArtifact(
            content=self.pdf,
            source_url=url,
            headers={
                "content-type": "application/pdf",
                "content-length": str(len(self.pdf)),
            },
            status_code=200,
        )


class FakeResponse:
    def __init__(
        self,
        *,
        content: bytes = b"",
        chunks: list[bytes] | None = None,
        status_code: int = 200,
        url: str = "https://www3.multco.us/viewimage/view_survey.aspx?docid=05335",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.content = content
        self.chunks = chunks
        self.status_code = status_code
        self.url = url
        self.headers = dict(
            headers
            or {
                "content-type": "text/html",
                "content-length": str(len(content)),
            }
        )
        self.history: list[FakeResponse] = []
        self.closed = False

    def iter_content(self, chunk_size: int) -> Any:
        del chunk_size
        if self.chunks is not None:
            yield from self.chunks
        else:
            yield self.content

    def close(self) -> None:
        self.closed = True


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []
        self.closed = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)

    def close(self) -> None:
        self.closed = True


def test_sources_preserve_eight_component_identities_and_alternatives() -> None:
    payload = sail.source_manifest()
    by_id = {source["source_id"]: source for source in payload["sources"]}

    assert tuple(by_id) == sail.SOURCE_IDS
    assert len(by_id) == 8
    assert by_id[sail.SURVEY_SOURCE_ID]["sort_tuple"] == ["OBJECTID"]
    assert by_id[sail.TAX_PARCEL_SOURCE_ID]["sort_tuple"] == ["OBJECTID_1"]
    assert by_id[sail.SURVEY_SOURCE_ID]["geometry"]["native"]["label"] == (
        "EPSG:2913"
    )
    assert by_id[sail.SUBDIVISION_SOURCE_ID]["geometry"]["native"]["label"] == (
        "EPSG:3857 (native WKID 102100)"
    )
    road_note = by_id[sail.ROAD_SOURCE_ID]["observed_contract"][
        "publisher_note"
    ]
    assert "does not represent a complete collection" in road_note
    complements = {
        item["name"] for item in payload["complementary_sources"]
    }
    assert "MultcoPropTax guest property search" in complements
    assert "DART standard reports and public-record requests" in complements
    assert "Multnomah County Surveyor assistance" in complements


def test_every_component_manifest_matches_live_identity_observations() -> None:
    expected_counts = {
        sail.SURVEY_SOURCE_ID: 87_179,
        sail.SUBDIVISION_SOURCE_ID: 6_314,
        sail.PARTITION_SOURCE_ID: 4_454,
        sail.CONDOMINIUM_SOURCE_ID: 1_720,
        sail.ROAD_SOURCE_ID: 4_439,
        sail.CORNER_SOURCE_ID: 8_997,
        sail.FIELD_BOOK_SOURCE_ID: 2_714,
        sail.TAX_PARCEL_SOURCE_ID: 284_039,
    }

    assert set(sail.COMPONENTS) == set(expected_counts)
    for source_id, component in sail.COMPONENTS.items():
        contract = component.manifest.contract_record()
        assert contract["source_id"] == source_id
        assert contract["service_item_id"] == component.item_id
        assert component.object_id_field in contract["required_fields"]
        assert component.observed_count == expected_counts[source_id]


def test_search_field_contract_is_source_specific_and_quotes_apostrophes() -> None:
    survey = sail.COMPONENTS[sail.SURVEY_SOURCE_ID]
    where, match = sail.build_where(
        survey,
        "Ladd's",
        field="subdivision",
        match="contains",
    )

    assert where == "SUBDIVISIO LIKE '%Ladd''s%'"
    assert match == "contains"
    with pytest.raises(sail.SourceSelectionError) as error:
        sail.build_where(
            survey,
            "R330254",
            field="property-id",
            match="exact",
        )
    assert error.value.code == "unsupported_field"


def test_oid_keyset_cursor_binds_full_query_and_returns_no_duplicates() -> None:
    client = FixtureClient()
    first = sail.execute(
        args_for(
            "search",
            "0533",
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--field",
            "survey-id",
            "--match",
            "contains",
            "--limit",
            "1",
            "--geometry",
        ),
        client=client,
        log_results=False,
    )

    assert first.status == ResultStatus.OK
    assert first.records[0]["object_id"] == 7220
    assert first.records[0]["geometry"]["output_crs"] == "EPSG:4326"
    assert first.next_cursor

    second = sail.execute(
        args_for(
            "search",
            "0533",
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--field",
            "survey-id",
            "--match",
            "contains",
            "--limit",
            "1",
            "--geometry",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert second.status == ResultStatus.OK
    assert [record["object_id"] for record in second.records] == [7221]
    assert second.next_cursor is None

    mismatch = sail.execute(
        args_for(
            "search",
            "0533",
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--field",
            "survey-id",
            "--match",
            "contains",
            "--limit",
            "1",
            "--cursor",
            first.next_cursor,
        ),
        client=client,
        log_results=False,
    )
    assert mismatch.status == ResultStatus.SOURCE_CHANGED
    assert mismatch.errors[0].code == "cursor_query_mismatch"


def test_omitted_limit_exhausts_keyset_pages_without_changing_transport_size() -> None:
    client = FixtureClient()
    args = args_for(
        "search",
        "0533",
        "--source",
        sail.SURVEY_SOURCE_ID,
        "--field",
        "survey-id",
        "--match",
        "contains",
    )
    result = sail.execute(args, client=client, log_results=False)

    assert args.limit is None
    assert [record["object_id"] for record in result.records] == [7220, 7221]
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None
    layer = client.layers[sail.SURVEY_SOURCE_ID]
    assert layer.record_counts == [1, 1, 1, 1]


def test_record_normalizes_survey_dates_identity_and_viewer_join() -> None:
    result = sail.execute(
        args_for(
            "record",
            "7220",
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--geometry",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert record["source_record_id"] == "7220"
    assert record["native_ids"]["SURVEYID"] == "05335"
    assert record["surveyor"] == "EWING, DONALD"
    assert record["dates"]["survey_date_raw"] == "1953/01/01"
    assert record["dates"]["file_date_raw"] == "1953/03/05"
    assert record["representations"][0]["url"].endswith("docid=05335")
    assert record["geometry"]["value"] == {
        "x": -122.63712608594447,
        "y": 45.56142433550407,
    }


def test_tax_parcel_preserves_parcel_ids_deed_join_and_assessor_map() -> None:
    result = sail.execute(
        args_for(
            "record",
            "1",
            "--source",
            sail.TAX_PARCEL_SOURCE_ID,
            "--geometry",
        ),
        client=FixtureClient(),
        log_results=False,
    )
    record = result.to_dict()["records"][0]

    assert record["native_ids"] == {
        "OBJECTID_1": 1,
        "PROPID": "R330254",
        "MAPTAXLOT": "1S1E21CB  -04600",
        "ALTACCTNUM": "R991212410",
    }
    assert record["native_parcel_id"] == "R330254"
    assert record["owners"] == ["LUMEN TECHNOLOGIES INC"]
    assert record["latest_deed_or_sale"]["instrument_number"] == "BP23830216"
    assert record["latest_deed_or_sale"]["deed_date_iso"].startswith(
        "2011-11-23"
    )
    assert record["representations"][0]["url"].endswith("1S1E21CB.pdf")
    assert record["join_candidates"]["portland_metro_regional_taxlots"][
        "relationship"
    ].endswith("shared_lineage")


def test_corner_and_field_book_keep_native_ids_and_image_joins() -> None:
    corner = sail.execute(
        args_for(
            "record",
            "1",
            "--source",
            sail.CORNER_SOURCE_ID,
        ),
        client=FixtureClient(),
        log_results=False,
    ).to_dict()["records"][0]
    field_book = sail.execute(
        args_for(
            "record",
            "1",
            "--source",
            sail.FIELD_BOOK_SOURCE_ID,
        ),
        client=FixtureClient(),
        log_results=False,
    ).to_dict()["records"][0]

    assert corner["native_ids"]["NEWBLMID"] == 400140
    assert corner["bearing_tree"]["book_page"] == "BT-A-100"
    assert corner["representations"][0]["url"].endswith("docid=PLC-1000")
    assert field_book["survey_document_id"] == "HURL-FB-01"
    assert field_book["representations"][0]["url"].endswith(
        "docid=HURL-FB-01"
    )


def test_image_viewer_normalizes_legacy_href_and_ignores_other_hosts() -> None:
    html = fixture_text("image_05335.html").replace(
        "</body>",
        '<a href="https://example.test/not-official.pdf">other</a></body>',
    )
    parsed = sail.parse_image_viewer(
        html,
        survey_id="05335",
        source_url=sail.image_viewer_url("05335"),
    )

    assert len(parsed["representations"]) == 1
    assert parsed["representations"][0]["pdf_url"] == (
        "https://www4.multco.us/Surveyimages/Survey/"
        "04000-05999/05335.PDF"
    )
    assert len(parsed["viewer_schema_fingerprint"]) == 64


def test_image_and_download_commands_preserve_both_representations(
    tmp_path: Path,
) -> None:
    client = FixtureClient()
    image = sail.execute(
        args_for(
            "image",
            "05335",
            "--source",
            sail.SURVEY_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )
    destination = tmp_path / "nested" / "05335.pdf"
    download = sail.execute(
        args_for(
            "download",
            "05335",
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--destination",
            str(destination),
        ),
        client=client,
        log_results=False,
    )

    assert image.status == ResultStatus.OK
    assert image.records[0]["viewer_bytes"] > 100
    assert download.status == ResultStatus.OK
    assert destination.read_bytes() == client.pdf
    assert download.records[0]["sha256"] == sail.hashlib.sha256(
        client.pdf
    ).hexdigest()
    assert download.raw_artifact_refs == (
        sail.image_viewer_url("05335"),
        "https://www4.multco.us/Surveyimages/Survey/"
        "04000-05999/05335.PDF",
    )


def test_bounded_streaming_closes_response_after_overflow() -> None:
    response = FakeResponse(
        chunks=[b"1234", b"5678"],
        headers={"content-type": "text/html"},
    )
    session = FakeSession([response])
    client = sail.MultnomahSAILClient(
        session=session,
        minimum_interval=0,
        retry_attempts=1,
        sleeper=lambda _seconds: None,
    )

    with pytest.raises(SourceSchemaError):
        client._request_bytes(
            sail.image_viewer_url("05335"),
            maximum_bytes=5,
            validator=client._validate_viewer_url,
            accept="text/html",
        )
    assert response.closed is True
    assert session.calls[0]["stream"] is True
    assert session.calls[0]["allow_redirects"] is True


def test_probe_all_validates_all_components_and_survey_resolver() -> None:
    result = sail.execute(
        args_for("probe", "--all"),
        client=FixtureClient(),
        log_results=False,
    )

    assert result["status"] == "ok"
    assert result["successful_components"] == 8
    assert [component["query"]["source"]["source_id"] for component in result[
        "components"
    ]] == list(sail.SOURCE_IDS)
    survey_probe = next(
        component
        for component in result["components"]
        if component["query"]["source"]["source_id"] == sail.SURVEY_SOURCE_ID
    )
    assert survey_probe["records"][0]["image_resolution"][
        "representations"
    ][0]["pdf_url"].endswith("05335.PDF")


def test_schema_drift_is_an_explicit_source_changed_result() -> None:
    component = sail.COMPONENTS[sail.SURVEY_SOURCE_ID]
    client = {
        sail.SURVEY_SOURCE_ID: FixtureLayerClient(
            component,
            missing_field="SURVEYID",
        )
    }
    result = sail.execute(
        args_for(
            "record",
            "7220",
            "--source",
            sail.SURVEY_SOURCE_ID,
        ),
        client=client,
        log_results=False,
    )

    assert result.status == ResultStatus.SOURCE_CHANGED
    assert result.errors[0].code == "source_schema_changed"


@pytest.mark.skipif(
    not LIVE,
    reason="set LIVE_PUBLIC_RECORDS=1 for official SAIL endpoint probes",
)
@pytest.mark.parametrize("source_id", sail.SOURCE_IDS)
def test_live_component_probe(source_id: str) -> None:
    result = sail.execute(
        args_for(
            "probe",
            "--source",
            source_id,
            "--no-resolve-image",
            "--minimum-interval",
            "0.05",
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    record = result.to_dict()["records"][0]
    assert record["component_total_count"] > 0
    assert record["max_record_count"] == 2_000
    assert len(record["schema_fingerprint"]) == 64


@pytest.mark.skipif(
    not LIVE,
    reason="set LIVE_PUBLIC_RECORDS=1 for official SAIL endpoint probes",
)
def test_live_known_survey_search_exhausts_exact_matches() -> None:
    result = sail.execute(
        args_for(
            "search",
            sail.KNOWN_SURVEY_ID,
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--field",
            "survey-id",
            "--match",
            "exact",
            "--minimum-interval",
            "0.05",
        ),
        log_results=False,
    )

    assert result.status == ResultStatus.OK
    assert [
        record["native_ids"]["SURVEYID"] for record in result.records
    ] == [sail.KNOWN_SURVEY_ID]
    assert result.next_cursor is None
    assert result.query.query.requested_limit is None


@pytest.mark.skipif(
    not LIVE,
    reason="set LIVE_PUBLIC_RECORDS=1 for official SAIL endpoint probes",
)
def test_live_known_survey_record_viewer_and_pdf(tmp_path: Path) -> None:
    record = sail.execute(
        args_for(
            "record",
            str(sail.KNOWN_SURVEY_OBJECT_ID),
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--geometry",
            "--minimum-interval",
            "0.05",
        ),
        log_results=False,
    )
    image = sail.execute(
        args_for(
            "image",
            sail.KNOWN_SURVEY_ID,
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--minimum-interval",
            "0.05",
        ),
        log_results=False,
    )
    destination = tmp_path / "05335.pdf"
    download = sail.execute(
        args_for(
            "download",
            sail.KNOWN_SURVEY_ID,
            "--source",
            sail.SURVEY_SOURCE_ID,
            "--destination",
            str(destination),
            "--minimum-interval",
            "0.05",
        ),
        log_results=False,
    )

    assert record.status == ResultStatus.OK
    assert record.records[0]["survey_document_id"] == sail.KNOWN_SURVEY_ID
    assert image.status == ResultStatus.OK
    assert download.status == ResultStatus.OK
    assert destination.stat().st_size == sail.KNOWN_SURVEY_PDF_BYTES
    assert download.records[0]["sha256"] == sail.KNOWN_SURVEY_PDF_SHA256
