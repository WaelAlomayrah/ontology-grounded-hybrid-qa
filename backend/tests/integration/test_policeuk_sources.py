from pathlib import Path

import pytest

from app.ingestion.policeuk_loader import CachedPoliceUKClient, download_ons_population


@pytest.mark.integration
def test_official_policeuk_availability_and_ons_population(tmp_path: Path) -> None:
    client = CachedPoliceUKClient(
        tmp_path,
        timeout=30,
        retries=2,
        user_agent="ontology-grounded-hybrid-qa-tests/0.1",
    )
    availability = client.get_json("https://data.police.uk/api/crimes-street-dates")
    assert availability
    assert availability[0]["date"]

    rows, files = download_ons_population(
        "https://www.nomisweb.co.uk/api/v01/dataset/NM_2014_1.data.csv",
        ["E01000001", "E01000002", "E01000003"],
        tmp_path,
        timeout=30,
        retries=2,
        user_agent="ontology-grounded-hybrid-qa-tests/0.1",
    )
    assert len(rows) == 3
    assert all(row["population"] > 0 for row in rows)
    assert files == ["ons-population-0001.csv"]
