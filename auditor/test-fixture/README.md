# Integration-test fixture — deliberately defective

This tree is the auditor integration ladder's test bed. Its artifacts carry **planted,
deliberately wrong content** inventoried in `census.json`; the full tier's oracle requires
a floor of those planted defects to be detected by the model audit, and the smoke tier
pins the census against this tree. Do not "fix" these files — a corrected fixture is a
broken test. The census test (`tests/test_auditor_fixture.py`) holds the two in step.
