"""The definition writer's parts; kit/schema_update.py is the entry point and runs the ILCE-1M2's pass (docs/decisions/0019).

    labels      the names values get: OCR slips mended, snapped to the definition's own, one name per code
    mirror      the memories' live copy: a field's memory set and offset, and its name
    notes       a note's evidence apart from what it says; a line added once
    fromdata    the parts taken from data/ alone (--from-data): the camera section, help, places, Expert marks
    proofs      a setting's evidence: what a rerun keeps, what backs each name, option trees, scaled numbers, the
                old lists of the values camera files held taken out (without_observed), the marks on the values no
                option was seen to write taken out (without_held), the records a proof wrote together taken out
                (without_written_with), a list of numbers sampled on a line, an array's one code table
    offered     the values the camera's menus never offer, each mark where its evidence holds; the values they offer
                under one video system only
    copies      the copies the camera keeps of a live value, where its downloads bear the rule out
    gate        --write's gate: the report's open questions against the camera's accepted file
    generic     the plain pass for any other camera, from a seed when it has no definition yet, with its hand tables
    hand_tables a camera's hand tables, read from its public data file (data/<model>_fw<fw>/hand_tables_*.json):
                what the mapping found by hand about the camera, in the shapes the writer reads
    hand_facts  the hand tables the plain pass reads, put on the definition (and the ones it refuses, which only the
                ILCE-1M2's pass reads so far)
    hand_evidence  a hand table's evidence, kept in the private overlay and put back into its tables when there; the
                stop when it is not there and the tables need it

kit/schema_update.py keeps the pass that reads the camera's runs (its main, and the readers of runs/<model>_fw<fw>/:
the help walks, the table walk, pass 1's map) and gives every name here under its old place (schema_update.clean),
which kit/pass2_report.py, the proof viewer and the tests import.
"""
