from hpo_drift.core import HP_ID
def test_id_regex():
    assert HP_ID.match("HP:0001369") and not HP_ID.match("HP:1")
