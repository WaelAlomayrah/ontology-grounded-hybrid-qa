# Police.uk public-safety dataset

## Purpose and safeguards

`policeuk` is an additive public-safety knowledge-retrieval dataset for descriptive incident, outcome, stop/search, geography, organisation, population, and rate questions. It does **not** predict crime, profile people, score individual risk, infer demographic risk, or rank individuals. Person-level stop/search demographics are deliberately excluded from RDF and Milvus.

## Official sources and licence

- [Police.uk downloads](https://data.police.uk/data/) provide monthly street crime, outcome history, and stop-and-search CSV data.
- [Police.uk API](https://data.police.uk/docs/) provides force identifiers, neighbourhoods, boundaries, and runtime availability.
- [ONS LSOA population estimates](https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/datasets/lowersuperoutputareamidyearpopulationestimatesnationalstatistics) and the official [ONS Nomis API](https://www.nomisweb.co.uk/api/v01/help) provide total population on 2021 LSOA geography.

All sources are used under the Open Government Licence v3.0. Police.uk updates monthly; ONS population estimates are annual. The loader queries official Nomis dataset `NM_2014_1`, geography `TYPE151`, latest time, total gender, and all ages in exact-code chunks. This avoids a fragile national-workbook download and retrieves only LSOAs present in the crime data.

Police.uk street coordinates are **anonymised approximate locations**, not actual incident locations. Point-in-polygon neighbourhood assignments inherit that limitation and are explicitly marked derived with their calculation method.

## Download and offline operation

The downloader asks the official availability endpoint for the newest complete months, downloads the official latest archive, inspects its members, and selects only the configured force/date/type files. API responses are cached with timeout, retry, exponential backoff, a clear User-Agent, and an inter-request delay.

Raw files remain unchanged under `data/policeuk/raw/`; normalized CSVs are written under `data/policeuk/processed/`. `manifest.json` records hashes, selected files, actual months, licence, counts, status, and provenance. After download, `--no-download` performs complete normalization and ingestion offline.

Online:

```bash
docker compose --profile tools run --rm data-loader \
  --dataset policeuk --reset --download --load-graph --load-vectors \
  --force "Thames Valley Police" --months 12
```

Offline:

```bash
docker compose --profile tools run --rm data-loader \
  --dataset policeuk --reset --no-download --load-graph --load-vectors \
  --force "Thames Valley Police" --months 12
```

Any official force name can be supplied with `--force`. The national archive is large; an official custom-download ZIP may instead be placed in `data/policeuk/raw/` for a smaller reliable demo.

## Joins and derived facts

Crime CSV `LSOA code` is authoritative for incident-to-LSOA links. ONS population joins use normalized exact code only, never textual area names. Outcome history joins only when a published `Crime ID` exactly matches a loaded crime; no fuzzy date/location/category matching is performed.

Neighbourhood links use official boundaries and point-in-polygon against the anonymised published point. Zero or multiple matches leave the relationship absent and increment the quality report.

Deterministic analytical observations include crime counts by LSOA/month/category, exact-linked outcome counts, stop/search counts by neighbourhood/month/object/outcome, and crime rate per 1,000 calculated as `count / ONS population * 1,000`. Rates store numerator, denominator, ONS reference year, method, and provenance. They are descriptive and do not imply causation.

## RDF and vector evidence

The ontology extension includes PoliceForce, Neighbourhood, LSOA, StreetLocation, CrimeIncident, CrimeCategory, OutcomeEvent, OutcomeCategory, StopSearchEvent, StopSearchOutcome, SearchObject, Legislation, PopulationObservation, CrimeAggregate, OutcomeAggregate, StopSearchAggregate, CrimeRateObservation, TimePeriod, and Boundary.

Every resource carries source dataset, record ID, file, retrieval time, licence, and derived status. Milvus receives readable incident, aggregate, outcome, stop/search, organisation, and LSOA evidence. The shared E5 service applies `passage:` and each semantic document stores its authoritative Fuseki graph URI.

## Reports and limitations

`data/policeuk/reports/latest.json` and `latest.md` report files, rows, events, LSOAs, population joins, triples, vector documents, duplicates, missing values, unmatched outcomes, spatial misses, unknown categories, API failures, and timings.

Limitations include approximate anonymised points, force/month differences in outcome and stop/search completeness, annual usually-resident population denominators, differing population/crime reference periods, and source revisions.

Example Arabic questions:

- `ما أكثر أنواع الجرائم المسجلة في مناطق أكسفورد خلال آخر 12 شهرا؟`
- `ما المناطق التي سجلت أعلى معدل لجرائم المركبات لكل ألف نسمة؟`
- `ما النتائج المسجلة لجرائم المركبات في المناطق ذات أعلى معدل؟`
- `اعرض الأدلة والعلاقات التي استخدمتها للوصول إلى هذه الإجابة.`
