# FedRAMP Rules (FRR) to OSCAL

This parses the JSON file published by FedRAMP containing the FedRAMP Rules and associated content. It creates an OSCAL Catalog with the FedRAMP Rules and FedRAMP Profiles for 20x Class A, B, C and D as well as Rev 5 Class B, C and D. (FedRAMP does not make Class A available under the Rev 5 path.)

## WORK IN PROGRESS  

The above description describes the target state. It is a work in progress.

### Working
- Creates an valid OSCAL Catalog with just the FedRAMP Rules
- Includes opinionated translation of some content to OSCAL
- Needs holistic review

### Up Next

- Additional refinement of the FRR -> OSCAL Content
- Quality Review and Revisions

### Roadmap

- KSIs to OSCAL Catalog
- 20x Path Profiles (classes A, B, C, and D)
- Rev 5 Path Profiles (Classes B, C and D)
- Refinement of Class D content when provided by the FedRAMP PMO
