import math
"""Toy-ontology tests: two hand-written releases where every expected change is known."""
import csv, json, pytest
from pathlib import Path
from hpo_drift import core, cli
from hpo_drift.core import Release, diff_terms, global_counts, similarity_drift, lint, read_terms, profile_drift, read_hpoa

OLD = """format-version: 1.2


[Term]
id: HP:0000001
name: All

[Term]
id: HP:0000118
name: Phenotypic abnormality
is_a: HP:0000001 ! All

[Term]
id: HP:0000010
name: Alpha
synonym: "Alpha thing" EXACT []
is_a: HP:0000118 ! Phenotypic abnormality

[Term]
id: HP:0000011
name: Alpha one
is_a: HP:0000010 ! Alpha

[Term]
id: HP:0000020
name: Beta
is_a: HP:0000118 ! Phenotypic abnormality

[Term]
id: HP:0000090
name: Old term
is_a: HP:0000020 ! Beta
"""
NEW = OLD.replace("name: Alpha one", "name: Alpha one renamed").replace(
    "id: HP:0000090\nname: Old term\nis_a: HP:0000020 ! Beta\n",
    "id: HP:0000090\nname: obsolete Old term\nis_obsolete: true\nreplaced_by: HP:0000011\n") + """
[Term]
id: HP:0000012
name: Alpha two
alt_id: HP:0000099
is_a: HP:0000010 ! Alpha
is_a: HP:0000020 ! Beta
"""


@pytest.fixture(scope="module")
def rels(tmp_path_factory):
    d = tmp_path_factory.mktemp("obo")
    (d / "old.obo").write_text(OLD); (d / "new.obo").write_text(NEW)
    return Release("vOLD", d / "old.obo"), Release("vNEW", d / "new.obo"), d


def test_resolve_and_ic(rels):
    old, new, _ = rels
    assert old.resolve("HP:0000010") == ("HP:0000010", "id")
    assert old.resolve("alpha thing") == ("HP:0000010", "label")
    assert new.resolve("HP:0000099") == ("HP:0000012", "alt_id")
    assert old.resolve("HP:0009999") == (None, "unknown-id") and old.resolve("Nope") == (None, "unknown-label")
    assert old.ic("HP:0000011") == 1.0 and old.ic("HP:0000118") == 0.0     # leaf / root of the IC domain (Phenotypic abnormality)
    assert math.isnan(old.ic("HP:0000001"))                                 # "All" sits above the domain root: no IC
    assert old.ic("HP:0000010") > old.ic("HP:0000118")
    assert new.ic("HP:0000010") < old.ic("HP:0000010"), "Alpha gained a descendant in the new release"


def test_diff_terms_statuses(rels):
    old, new, _ = rels
    st = {c.tid: c for c in diff_terms(old, new, ["HP:0000010", "HP:0000011", "HP:0000090", "HP:0000020"])}
    assert st["HP:0000010"].status == "unchanged"
    assert st["HP:0000011"].status == "renamed" and st["HP:0000011"].new_name == "Alpha one renamed"
    assert st["HP:0000090"].status == "obsoleted" and st["HP:0000090"].replaced_by == ["HP:0000011"]
    assert abs(st["HP:0000010"].ic_delta) > 0 and st["HP:0000010"].status == "unchanged", "IC drift without any edit to the term"


def test_global_counts(rels):
    old, new, _ = rels
    g = global_counts(old, new)
    assert g["added"] == 1 and g["obsoleted"] == 1 and g["renamed"] == 1
    assert g["is_a_added"] == 2 and g["is_a_removed"] == 1


def test_similarity_drift(rels):
    old, new, _ = rels
    ids = ["HP:0000010", "HP:0000011", "HP:0000020"]
    pairs = similarity_drift(old, new, ids)
    assert len(pairs) == 3
    p = next(x for x in pairs if {x.a, x.b} == {"HP:0000010", "HP:0000011"})
    assert p.mica_old == "HP:0000010" and abs(p.lin_delta) > 0
    assert old.lin("HP:0000011", "HP:0000011") == 1.0 and old.resnik("HP:0000010", "HP:0000020") == old.ic("HP:0000118")


def test_lint(rels, tmp_path):
    old, new, _ = rels
    f = tmp_path / "t.txt"; f.write_text("# comment\nHP:0000010\nAlpha thing\nHP:0000090\nHP:0000099\nUnicorn\n")
    issues = {i.token: i for i in lint(new, read_terms(str(f)))}
    assert issues["Alpha thing"].level == "warn" and issues["Alpha thing"].suggestion.startswith("HP:0000010")
    assert issues["HP:0000090"].level == "error" and "HP:0000011" in (issues["HP:0000090"].suggestion or "")
    assert issues["Unicorn"].level == "error"
    assert "HP:0000010" not in issues


def test_cli_report_and_lint(rels, tmp_path, monkeypatch, capsys):
    old, new, d = rels
    monkeypatch.setattr(core, "fetch", lambda tag: {"vOLD": d / "old.obo", "vNEW": d / "new.obo"}[tag])
    f = tmp_path / "t.txt"; f.write_text("HP:0000010\nHP:0000011\nHP:0000020\n")
    cli.main(["report", "--old", "vOLD", "--new", "vNEW", "--terms", str(f), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert out["global"]["renamed"] == 1 and len(out["terms"]) == 3 and len(out["pairs"]) == 3
    cli.main(["report", "--old", "vOLD", "--new", "vNEW", "--terms", str(f)])
    txt = capsys.readouterr().out
    assert "renamed" in txt and "Alpha one" in txt
    cli.main(["lint", "--release", "vNEW", "--terms", str(f)])
    assert "clean" in capsys.readouterr().out
    cli.main(["lint", "--release", "vNEW", "--terms", str(f), "--json"])
    assert json.loads(capsys.readouterr().out) == []


def test_pair_kinds_and_out_of_domain(rels):
    old, new, _ = rels
    pairs = {frozenset((p.a, p.b)): p for p in similarity_drift(old, new, ["HP:0000010", "HP:0000020", "HP:0000011"])}
    assert pairs[frozenset(("HP:0000010", "HP:0000020"))].kind == "ROOT_ONLY"        # share only Phenotypic abnormality
    assert pairs[frozenset(("HP:0000010", "HP:0000011"))].kind == "INFORMATIVE"
    p = pairs[frozenset(("HP:0000010", "HP:0000020"))]; assert p.lin_old == 0 and p.lin_new == 0
    st = {c.tid: c for c in diff_terms(old, new, ["HP:0000001", "HP:0000010"])}
    assert st["HP:0000001"].domain == "OUT_OF_DOMAIN" and st["HP:0000010"].domain == "in"   # "All" is above the root
    assert similarity_drift(old, new, ["HP:0000001", "HP:0000010"]) == []                    # out-of-domain terms enter no pair


def test_profile_statuses(rels):
    old, new, _ = rels
    assert profile_drift(old, new, [])["status"] == "NO_USABLE_TERMS"
    assert profile_drift(old, new, ["HP:0000001", "HP:0009999"])["status"] == "NO_USABLE_TERMS"     # out of domain + missing
    r = profile_drift(old, new, ["HP:0000010", "HP:0000010"]); assert r["status"] == "TERM_ONLY" and r["n_raw_terms"] == 1 and math.isnan(r["mean_abs_dlin"])
    r = profile_drift(old, new, ["HP:0000010", "HP:0000020"]); assert r["status"] == "NO_INFORMATIVE_PAIRS" and r["n_root_only_pairs"] == 1
    r = profile_drift(old, new, ["HP:0000010", "HP:0000011", "HP:0000020", "HP:0000090", "HP:0000001"])
    assert r["status"] == "RANKABLE" and r["n_retained_terms"] == 3 and r["n_obsolete"] == 1 and r["n_out_of_domain"] == 1
    assert r["n_pairs"] == 3 and r["n_informative_pairs"] == 1 and r["n_root_only_pairs"] == 2 and r["max_abs_dlin"] > 0


def test_cli_report_edge_cases(rels, tmp_path, monkeypatch, capsys):
    old, new, d = rels
    monkeypatch.setattr(core, "fetch", lambda tag: {"vOLD": d / "old.obo", "vNEW": d / "new.obo"}[tag])
    f = tmp_path / "one.txt"; f.write_text("HP:0000010\nHP:0000001\n")
    cli.main(["report", "--old", "vOLD", "--new", "vNEW", "--terms", str(f)]); txt = capsys.readouterr().out
    assert "OUT_OF_DOMAIN" in txt and "--root" in txt and "Single usable term" in txt
    f.write_text("HP:0000010\nHP:0000020\n")
    cli.main(["report", "--old", "vOLD", "--new", "vNEW", "--terms", str(f)]); txt = capsys.readouterr().out
    assert "ROOT_ONLY" in txt and "NO_INFORMATIVE_PAIRS" in txt
    f.write_text("Unicorn\n")
    cli.main(["report", "--old", "vOLD", "--new", "vNEW", "--terms", str(f)]); assert "No usable terms" in capsys.readouterr().out


def test_cohort_and_rank(rels, tmp_path, monkeypatch, capsys):
    old, new, d = rels
    monkeypatch.setattr(core, "fetch", lambda tag: {"vOLD": d / "old.obo", "vNEW": d / "new.obo"}[tag])
    h = tmp_path / "phenotype.hpoa"
    hdr = "#version: 2099-01-01\ndatabase_id\tdisease_name\tqualifier\thpo_id\treference\tevidence\tonset\tfrequency\tsex\tmodifier\taspect\tbiocuration\n"
    row = lambda db, t, asp="P", q="": f"{db}\tDisease {db}\t{q}\t{t}\tPMID:1\tPCS\t\t\t\t\t{asp}\tx\n"
    h.write_text(hdr + row("OMIM:1", "HP:0000010") + row("OMIM:1", "HP:0000011") + row("OMIM:1", "HP:0000020") + row("OMIM:1", "HP:0000001", "I")
                 + row("OMIM:2", "HP:0000010") + row("OMIM:2", "HP:0000020") + row("ORPHA:3", "HP:0000010") + row("ORPHA:4", "HP:0000090") + row("ORPHA:5", "HP:0000011", q="NOT"))
    meta, prof = read_hpoa(str(h)); assert meta["version"] == "2099-01-01" and prof["OMIM:1"][1] == ["HP:0000010", "HP:0000011", "HP:0000020"] and "ORPHA:5" not in prof
    out = tmp_path / "all.csv"
    cli.main(["cohort", "--hpoa", str(h), "--old", "vOLD", "--new", "vNEW", "--out", str(out)])
    rows = {r["disease"]: r for r in csv.DictReader(open(out))}
    assert {rows[k]["status"] for k in rows} == {"RANKABLE", "NO_INFORMATIVE_PAIRS", "TERM_ONLY", "NO_USABLE_TERMS"} and len(rows) == 4
    assert rows["OMIM:1"]["status"] == "RANKABLE" and rows["OMIM:2"]["status"] == "NO_INFORMATIVE_PAIRS" and rows["ORPHA:3"]["status"] == "TERM_ONLY" and rows["ORPHA:4"]["status"] == "NO_USABLE_TERMS"
    assert json.load(open(str(out) + ".meta.json"))["status_counts"]["RANKABLE"] == 1
    capsys.readouterr()
    cli.main(["rank", str(out), "--metric", "mean_abs_dlin"]); o = capsys.readouterr()
    ranked = list(csv.DictReader(o.out.splitlines())); assert len(ranked) == 1 and ranked[0]["rank"] == "1" and ranked[0]["disease"] == "OMIM:1"
    assert "1 RANKABLE of 4" in o.err
