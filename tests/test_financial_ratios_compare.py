import json

from tools.financial_ratios import compare_multiple


def _ratio_file(tmp_path, company, value):
    path = tmp_path / f"{company}.json"
    path.write_text(json.dumps({
        "company": company,
        "ratios": [{"period": "2025", "gross_margin_pct": value}],
    }))
    return path


def test_small_cohort_outlier_reports_half_range_method(tmp_path):
    paths = [
        _ratio_file(tmp_path, company, value)
        for company, value in zip(("A", "B", "C", "D"), (0, 0, 0, 100))
    ]

    result = compare_multiple(paths)
    outlier = next(row for row in result["outliers"] if row["company"] == "D")

    assert outlier["outlier_score"] == 2.0
    assert outlier["score_method"] == "median_deviation_over_half_range"
    assert outlier["threshold"] == 1.5
    assert outlier["sample_size"] == 4
    assert "z_score" not in outlier


def test_larger_cohort_outlier_reports_population_stddev_method(tmp_path):
    paths = [
        _ratio_file(tmp_path, company, value)
        for company, value in zip(("A", "B", "C", "D", "E"), (0, 0, 0, 0, 100))
    ]

    result = compare_multiple(paths)
    outlier = next(row for row in result["outliers"] if row["company"] == "E")

    assert outlier["outlier_score"] == 2.5
    assert outlier["score_method"] == "median_deviation_over_population_stddev"
    assert outlier["threshold"] == 2.0
    assert outlier["sample_size"] == 5
