import pandas as pd

from experimental_qc.config import GroupSize, NumericRange, QCConfig
from experimental_qc.qc import run_qc


def test_clean_data_passes():
    df = pd.DataFrame(
        {
            "sample_id": ["S1", "S2", "S3", "S4"],
            "condition": ["control", "control", "treated", "treated"],
            "signal": [10.0, 11.0, 14.0, 15.0],
        }
    )
    config = QCConfig(
        id_column="sample_id",
        required_columns=("sample_id", "condition", "signal"),
        numeric_ranges={"signal": NumericRange(0, 100)},
        categorical_columns=("condition",),
        group_column="condition",
        expected_group_size=GroupSize(2, 2),
        outlier_columns=("signal",),
    )

    result = run_qc(df, config)

    assert result.status == "PASS"
    assert result.issues.empty


def test_detects_missing_duplicate_and_range_issues():
    df = pd.DataFrame(
        {
            "sample_id": ["S1", "S1", None, "S4"],
            "signal": [10.0, -2.0, None, "bad"],
        }
    )
    config = QCConfig(
        id_column="sample_id",
        required_columns=("sample_id", "signal"),
        numeric_ranges={"signal": NumericRange(0, 100)},
    )

    result = run_qc(df, config)
    issue_types = set(result.issues["issue_type"])

    assert {"duplicate_id", "missing_required", "out_of_range", "non_numeric"} <= issue_types


def test_detects_inconsistent_case_and_whitespace():
    df = pd.DataFrame({"condition": ["Control", "control", " Control ", "treated"]})
    config = QCConfig(categorical_columns=("condition",))

    result = run_qc(df, config)

    flagged = result.issues[result.issues["issue_type"] == "inconsistent_label"]
    assert len(flagged) == 3


def test_detects_iqr_outlier():
    df = pd.DataFrame({"signal": [10, 10, 11, 11, 12, 100]})
    config = QCConfig(outlier_columns=("signal",))

    result = run_qc(df, config)

    outliers = result.issues[result.issues["issue_type"] == "statistical_outlier"]
    assert outliers["value"].tolist() == [100]
