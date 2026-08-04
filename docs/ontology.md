# Sample ontology

The `org:` vocabulary defines Person/Employee, OrganizationalUnit/Department, Project, InformationSystem, Vendor, and Location. Object properties declare domains/ranges and inverses for employment, management, and ownership. Instances are generated from CSV; they are not duplicated in the ontology source.

## Public-safety extension

The `policeuk:` vocabulary is added to the same authoritative Fuseki graph when
`policeuk` is active. It models police organisation, 2021 LSOAs, anonymised
locations, incidents, controlled categories, exact-linked outcomes, stop/search
events, ONS population observations, aggregates, rates, and time. Major concepts
and crime categories have English and Arabic labels.

Core paths include:

- `CrimeIncident -> locatedIn -> LSOA -> hasPopulationObservation -> PopulationObservation`
- `CrimeIncident -> hasOutcome -> OutcomeEvent -> outcomeCategory -> OutcomeCategory`
- `StopSearchEvent -> occurredAt -> StreetLocation -> withinNeighbourhood -> Neighbourhood -> partOf -> PoliceForce`

Source and derived resources carry record/file/licence/retrieval provenance.
Spatial assignments and aggregates are explicitly identified as derived. See
[Police.uk dataset](policeuk-dataset.md).
