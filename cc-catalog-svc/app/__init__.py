"""cc-catalog-svc — self-contained CodeCollection image catalog + mirror.

See README.md for the architecture overview. The TL;DR is:

    sources  -->  catalog DB  -->  /api/v1/catalog/* (PAPI contract)
                       |
                       +-->  mirror engine (crane copy)  -->  destinations

This service is intentionally additive to the existing cc-registry-v2 image
catalog: same source-plugin contract, same PAPI-facing API shape, but with
an extra destination-plugin concept (JFrog Artifactory in v1) and no Celery
/ Redis dependency. One container, one process.
"""

__version__ = "0.1.0"
