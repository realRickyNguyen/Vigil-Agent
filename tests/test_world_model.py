"""Tests for the World Model engine (app/engines/world_model.py). No network.

The first eight tests port the Meterless World Model conformance runner
(github.com/Meterless/Meterless, engines/world-model/conformance/runner.ts) case by case,
with the same inputs and the same assertions. The rest cover what Vigil adds on top:
decisions that depend on facts, reopened when a supporting fact is superseded."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.engines.world_model import (  # noqa: E402
    ProvenanceError, WorldModel, decide, entity_id_from_name, normalize_name)

CLOCK = "2026-05-18T00:00:00.000Z"
OBSERVATIONS = [
    {"externalId": "a1", "title": "Fed holds rates", "at": "2026-05-17T14:00:00.000Z",
     "source": {"kind": "rss", "at": "2026-05-17T14:00:00.000Z"},
     "entities": [{"type": "person", "name": "Jerome Powell"}]},
    {"externalId": "a2", "title": "Powell signals patience", "at": "2026-05-17T16:30:00.000Z",
     "source": {"kind": "rss", "at": "2026-05-17T16:30:00.000Z"},
     "entities": [{"type": "person", "name": "Jerome Powell"}]},
]


def manual(at):
    return {"kind": "manual", "at": at}


# Conformance: runner.ts, one test per case id.

def test_sid_001_diacritics_and_nbsp_normalize_identically():
    assert normalize_name("José  García") == normalize_name("Jose Garcia")
    assert entity_id_from_name("person", "José García") == entity_id_from_name("person", "jose garcia")


def test_sid_002_distinct_names_stay_distinct():
    assert entity_id_from_name("org", "Acme Corp") != entity_id_from_name("org", "Acme Corporation")
    assert entity_id_from_name("person", "x") != entity_id_from_name("org", "x")


def test_band_001_merge_bands_at_the_boundaries():
    assert decide(0.85) == "auto-merge"
    assert decide(0.84) == "review"
    assert decide(0.82) == "review"
    assert decide(0.81) == "new"


def test_prov_001_writes_without_provenance_are_rejected():
    world = WorldModel(namespace="conf")
    with pytest.raises(ProvenanceError):
        world.upsert_entity(type="person", name="No Provenance", source=None)
    with pytest.raises(ProvenanceError):
        world.upsert_entity(type="person", name="No Time", source={"kind": "manual"})


def test_idem_001_same_batch_twice_produces_an_empty_diff():
    world = WorldModel(namespace="conf", clock=lambda: CLOCK)
    world.ingest(OBSERVATIONS)
    shape1 = world.state_shape_canonical()
    second = world.ingest(OBSERVATIONS)
    assert second["changed"] is False
    assert world.state_shape_canonical() == shape1


def test_idem_002_a_mutated_batch_changes_the_shape():
    world = WorldModel(namespace="conf", clock=lambda: CLOCK)
    world.ingest(OBSERVATIONS)
    shape1 = world.state_shape_canonical()
    mutated = [{**OBSERVATIONS[0], "title": OBSERVATIONS[0]["title"] + " (edited)"}, OBSERVATIONS[1]]
    run = world.ingest(mutated)
    assert run["changed"] is True
    assert world.state_shape_canonical() != shape1


def test_bitemp_001_superseding_edge_closes_the_old_one():
    world = WorldModel(namespace="conf")
    world.upsert_entity(type="player", external_key={"system": "g", "id": "p1"}, attrs={},
                        source=manual("2087-01-01T00:00:00.000Z"))
    world.upsert_entity(type="team", external_key={"system": "g", "id": "a"}, attrs={},
                        source=manual("2087-01-01T00:00:00.000Z"))
    world.upsert_entity(type="team", external_key={"system": "g", "id": "b"}, attrs={},
                        source=manual("2088-03-01T00:00:00.000Z"))
    world.relate(src="player:g:p1", type="plays-for", dst="team:g:a", valid_from="2087-01-01T00:00:00.000Z",
                 source=manual("2087-01-01T00:00:00.000Z"))
    world.relate(src="player:g:p1", type="plays-for", dst="team:g:b", valid_from="2088-03-01T00:00:00.000Z",
                 source=manual("2088-03-01T00:00:00.000Z"))
    graph = world.view("graph")
    assert [e["id"] for e in graph.neighbors_of("player:g:p1", via="plays-for")] == ["team:g:b"]
    assert [e["id"] for e in graph.neighbors_of("player:g:p1", via="plays-for",
                                                at="2087-06-01T00:00:00.000Z")] == ["team:g:a"]


def test_audit_001_every_mutation_writes_an_audit_entry_in_order():
    world = WorldModel(namespace="conf")
    world.upsert_entity(type="x", name="Audit One", source=manual("2026-01-01T00:00:00.000Z"))
    world.upsert_entity(type="x", name="Audit Two", source=manual("2026-01-02T00:00:00.000Z"))
    audit = world.audit()
    assert len(audit) >= 2
    assert all(b["seq"] > a["seq"] for a, b in zip(audit, audit[1:]))


# Vigil behaviour: decisions depend on facts and reopen when a fact is superseded.

def label_world(effective_time="20240101"):
    world = WorldModel(namespace="bb")
    drug = world.upsert_entity(type="drug", name="montelukast", source=manual("2026-10-22T00:00:00.000Z"))
    label = world.assert_fact(about=drug["id"], predicate="label_version", value=effective_time,
                              source=manual("2026-10-22T00:00:00.000Z"))
    return world, drug, label


def test_changed_label_version_reopens_a_dependent_not_covered_verdict():
    world, drug, label = label_world("20240101")
    world.record_decision(key="montelukast|SLEEP APNOEA SYNDROME", about=drug["id"],
                          value={"label_coverage": "not_found", "workflow_status": "reviewed"},
                          depends_on=[label["id"]], source=manual("2026-10-22T01:00:00.000Z"))
    assert [d["status"] for d in world.decisions()] == ["current"]

    world.assert_fact(about=drug["id"], predicate="label_version", value="20260901",
                      source=manual("2026-10-23T00:00:00.000Z"))

    reopened = world.decisions(status="reopened")
    assert [d["key"] for d in reopened] == ["montelukast|SLEEP APNOEA SYNDROME"]
    assert reopened[0]["reopened_because"]["superseded_fact"] == label["id"]
    assert any(a["kind"] == "reopen" for a in world.audit())


def test_same_label_version_again_reopens_nothing():
    world, drug, label = label_world("20240101")
    world.record_decision(key="montelukast|ASTHMA", about=drug["id"],
                          value={"label_coverage": "covered"}, depends_on=[label["id"]],
                          source=manual("2026-10-22T01:00:00.000Z"))
    again = world.assert_fact(about=drug["id"], predicate="label_version", value="20240101",
                              source=manual("2026-10-22T00:00:00.000Z"))
    assert again["id"] == label["id"]
    assert world.decisions(status="reopened") == []


def test_decision_needs_provenance_and_known_facts():
    world, drug, label = label_world()
    with pytest.raises(ProvenanceError):
        world.record_decision(key="k", about=drug["id"], value={}, depends_on=[label["id"]], source=None)
    with pytest.raises(KeyError):
        world.record_decision(key="k", about=drug["id"], value={}, depends_on=["fact_missing"],
                              source=manual("2026-10-22T01:00:00.000Z"))


def queue_item(reaction, coverage, status="reviewed"):
    return {"reaction": reaction, "label_coverage": coverage, "context": "clinical_event",
            "review_priority": "review_next" if coverage == "not_found" else "lower_priority",
            "workflow_status": status}


def test_pipeline_reopens_earlier_verdicts_when_the_label_changes(tmp_path):
    from app.orchestration.pipeline import remember
    path = tmp_path / "world.json"
    queue = [queue_item("SLEEP APNOEA SYNDROME", "not_found"), queue_item("ASTHMA", "covered"),
             queue_item("NAUSEA", "not_found", status="pending")]
    first = remember(WorldModel("bb", path), "montelukast", {"set_id": "s1", "effective_time": "20240101"},
                     queue, "run-1", "2026-10-22T01:00:00+00:00")
    assert first["decisions_recorded"] == 2  # the pending item was never settled, so nothing rests on it
    assert first["reopened"] == []

    same = remember(WorldModel("bb", path), "montelukast", {"set_id": "s1", "effective_time": "20240101"},
                    [], "run-2", "2026-10-22T02:00:00+00:00")
    assert same["reopened"] == [] and same["label_fact"] == first["label_fact"]

    changed = remember(WorldModel("bb", path), "montelukast", {"set_id": "s1", "effective_time": "20260901"},
                       [], "run-3", "2026-10-23T01:00:00+00:00")
    assert sorted(r["reaction"] for r in changed["reopened"]) == ["ASTHMA", "SLEEP APNOEA SYNDROME"]
    assert all(r["earlier_run"] == "run-1" for r in changed["reopened"])


def test_state_survives_a_save_and_reload(tmp_path):
    path = tmp_path / "world.json"
    world = WorldModel(namespace="bb", path=path)
    drug = world.upsert_entity(type="drug", name="montelukast", source=manual("2026-10-22T00:00:00.000Z"))
    world.assert_fact(about=drug["id"], predicate="label_version", value="20240101",
                      source=manual("2026-10-22T00:00:00.000Z"))
    shape = world.state_shape_canonical()
    reloaded = WorldModel(namespace="bb", path=path)
    assert reloaded.state_shape_canonical() == shape
    assert [e["seq"] for e in reloaded.events()] == [e["seq"] for e in world.events()]
