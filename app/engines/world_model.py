"""Meterless World Model engine: event-sourced shared state for agents, ported to Python.

Follows the Meterless reference (github.com/Meterless/Meterless, engines/world-model, Apache-2.0):
stable IDs, merge bands, provenance required on every write, idempotent ingest, bitemporal edges
and a strictly increasing audit sequence. tests/test_world_model.py ports its conformance runner.

Black Box adds decisions: an agent's verdict is recorded with the facts it rests on, and when a
newer fact supersedes one of them (for example a new label version), the verdict is reopened
instead of silently standing. The reference has no dependency tracking, so this part is ours.

Everything is derived from the append-only event log, so a saved world reloads by replaying it.
Timestamps come from each write's provenance, never the wall clock."""
import hashlib
import json
import re
import threading
import unicodedata
from pathlib import Path

AUTO_MERGE_AT = 0.85
REVIEW_LOWER = 0.82
CLUSTER_JACCARD = 0.5


class ProvenanceError(ValueError):
    """A write arrived without a source saying what produced it and when."""


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(value) -> str:
    """Sorted keys, no whitespace, None members dropped: the same value always gives the same string."""
    if isinstance(value, dict):
        items = sorted((k, v) for k, v in value.items() if v is not None)
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical_json(v) for k, v in items) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(canonical_json(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def normalize_name(name: str) -> str:
    """NFKD, strip combining marks and zero-width characters, lowercase, collapse whitespace."""
    s = unicodedata.normalize("NFKD", name)
    s = re.sub("[̀-ͯ]", "", s)
    s = re.sub("[​-‍﻿]", "", s)
    return re.sub(r"\s+", " ", s.lower()).strip()


def entity_id_from_name(type: str, name: str) -> str:
    return "ent_" + sha256_hex(f"{type}:{normalize_name(name)}")[:16]


def external_id(type: str, system: str, id: str) -> str:
    return f"{type}:{system}:{id}"


def decide(similarity: float, auto_merge_at: float = AUTO_MERGE_AT, review_lower: float = REVIEW_LOWER) -> str:
    """Merge band for a name match. Both boundaries are inclusive: 0.85 auto-merges, 0.82 queues."""
    if similarity >= auto_merge_at:
        return "auto-merge"
    if similarity >= review_lower:
        return "review"
    return "new"


def similarity(a: str, b: str) -> float:
    """1 - Levenshtein distance / longer length, on normalized names."""
    a, b = normalize_name(a), normalize_name(b)
    if not a and not b:
        return 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return 1 - prev[-1] / max(len(a), len(b))


def jaccard(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def check_source(source) -> dict:
    if not isinstance(source, dict) or not source.get("kind") or not source.get("at"):
        raise ProvenanceError("every write needs source={'kind': ..., 'at': ...}")
    return dict(source)


class Graph:
    """Read view over relationships."""

    def __init__(self, world: "WorldModel"):
        self.world = world

    def neighbors_of(self, id: str, via: str | None = None, at: str | None = None) -> list[dict]:
        """Entities this one points to. Without `at`, only open edges; with it, edges valid at that instant."""
        out = []
        for r in self.world.state["relationships"].values():
            if r["from"] != id or (via and r["type"] != via):
                continue
            if at is None:
                if r.get("validTo"):
                    continue
            elif not ((r.get("validFrom") or "") <= at and (not r.get("validTo") or at < r["validTo"])):
                continue
            ent = self.world.state["entities"].get(r["to"])
            if ent:
                out.append(ent)
        return sorted(out, key=lambda e: e["id"])


class WorldModel:
    """One namespace of shared state. Writes are serialised by a lock, so parallel agents append in a
    single total order; with `path`, the event log and audit are saved after every write."""

    def __init__(self, namespace: str = "default", path: str | Path | None = None, clock=None):
        self.namespace = namespace
        self.path = Path(path) if path else None
        self.clock = clock
        self._lock = threading.RLock()
        self._events: list[dict] = []
        self._audit: list[dict] = []
        self.merge_queue: list[dict] = []
        self.state = self._empty()
        if self.path and self.path.exists():
            saved = json.loads(self.path.read_text(encoding="utf-8"))
            for event in saved.get("events", []):
                self._events.append(event)
                self._fold(event)
            self._audit = saved.get("audit", [])

    @staticmethod
    def _empty() -> dict:
        return {"entities": {}, "relationships": {}, "facts": {}, "aliases": {}, "observations": {},
                "stories": {}, "decisions": {}}

    # Event log

    def _append(self, kind: str, payload: dict, actor: str, summary: str, at: str) -> dict:
        event = {"id": f"evt_{len(self._events) + 1}", "seq": len(self._events) + 1, "kind": kind,
                 "payload": payload, "schemaVersion": 1, "at": at}
        self._events.append(event)
        effects = self._fold(event)
        self._write_audit(kind, actor, summary, at, event["id"])
        for d in effects:
            self._write_audit("reopen", actor, f"reopened {d['key']}: {d['reopened_because']['superseded_fact']} "
                              f"superseded by {d['reopened_because']['by_fact']}", at, event["id"])
        self._save()
        return event

    def _write_audit(self, kind, actor, summary, at, event_id=None):
        seq = self._audit[-1]["seq"] + 1 if self._audit else 1
        self._audit.append({"seq": seq, "at": at, "kind": kind, "actor": actor, "summary": summary,
                            "eventId": event_id})

    def _save(self):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"namespace": self.namespace, "events": self._events, "audit": self._audit},
                                      ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)

    def _fold(self, event: dict) -> list[dict]:
        """Apply one event to the state. Returns decisions it reopened, so the writer can audit them."""
        s, p, kind = self.state, event["payload"], event["kind"]
        if kind == "upsertEntity":
            old = s["entities"].get(p["id"])
            if old:
                old["attrs"] = {**old["attrs"], **p["attrs"]}
                old["updatedAt"] = p["updatedAt"]
                if p.get("name"):
                    old["name"] = p["name"]
            else:
                s["entities"][p["id"]] = json.loads(json.dumps(p))
        elif kind == "relate":
            for other in s["relationships"].values():
                if (other["from"] == p["from"] and other["type"] == p["type"]
                        and (other.get("context") or "") == (p.get("context") or "")
                        and other["to"] != p["to"] and not other.get("validTo") and not other.get("supersededBy")):
                    other["validTo"] = p.get("validFrom") or p["createdAt"]
                    other["supersededBy"] = p["id"]
            s["relationships"].setdefault(p["id"], json.loads(json.dumps(p)))
        elif kind == "assertFact":
            if p["id"] in s["facts"]:
                return []
            s["facts"][p["id"]] = json.loads(json.dumps(p))
            # Most recent wins for one (about, predicate): an older fact with a different value is
            # superseded, and every decision resting on it is reopened.
            reopened = []
            for old in s["facts"].values():
                if (old["id"] != p["id"] and old["about"] == p["about"] and old["predicate"] == p["predicate"]
                        and not old.get("supersededBy") and old["assertedAt"] <= p["assertedAt"]):
                    old["supersededBy"] = p["id"]
                    for d in s["decisions"].values():
                        if d["status"] == "current" and old["id"] in d["dependsOn"]:
                            d["status"] = "reopened"
                            d["reopened_because"] = {"superseded_fact": old["id"], "by_fact": p["id"]}
                            reopened.append(d)
            return reopened
        elif kind == "alias":
            s["aliases"][p["aliasId"]] = p["primaryId"]
        elif kind == "observe":
            s["observations"][p["externalId"]] = json.loads(json.dumps(p))
            s["stories"] = self._stories()
        elif kind == "recordDecision":
            s["decisions"][p["key"]] = {**json.loads(json.dumps(p)), "status": "current"}
        return []

    def _stories(self) -> dict:
        """Group observations into stories by overlap of the entities they mention."""
        obs = sorted(self.state["observations"].values(), key=lambda o: o["externalId"])
        used, stories = set(), {}
        for seed in obs:
            if seed["externalId"] in used:
                continue
            group = [seed["externalId"]]
            used.add(seed["externalId"])
            for other in obs:
                if other["externalId"] not in used and jaccard(seed["entityIds"], other["entityIds"]) >= CLUSTER_JACCARD:
                    group.append(other["externalId"])
                    used.add(other["externalId"])
            sid = "story_" + sha256_hex(canonical_json(sorted(group)))[:12]
            stories[sid] = {"id": sid, "members": sorted(group)}
        return stories

    # Writes

    def upsert_entity(self, type: str, source, name: str | None = None, external_key: dict | None = None,
                      attrs: dict | None = None, actor: str = "app", resolve: bool = True) -> dict:
        source = check_source(source)
        with self._lock:
            if external_key:
                eid = external_id(type, external_key["system"], external_key["id"])
            elif name:
                eid = entity_id_from_name(type, name)
                if resolve and eid not in self.state["entities"]:
                    eid = self._resolve(type, name, eid, source)
            else:
                raise ValueError("an entity needs a name or an external_key")
            eid = self.state["aliases"].get(eid, eid)
            payload = {"type": type, "id": eid, "name": name, "attrs": attrs or {}, "schemaVersion": 1,
                       "source": source, "createdAt": source["at"], "updatedAt": source["at"], "state": "active"}
            self._append("upsertEntity", payload, actor, f"upsert {type} {name or eid}", source["at"])
            return self.state["entities"][eid]

    def _resolve(self, type, name, eid, source) -> str:
        """Compare a new name with existing entities of the same type: merge, queue for review, or keep new."""
        best, best_sim = None, 0.0
        for e in self.state["entities"].values():
            if e["type"] == type and e.get("name"):
                sim = similarity(name, e["name"])
                if sim > best_sim:
                    best, best_sim = e, sim
        band = decide(best_sim) if best else "new"
        if band == "auto-merge":
            self._append("alias", {"aliasId": eid, "primaryId": best["id"], "mergedAt": source["at"],
                                   "mergedBy": "resolver", "reason": f"similarity {best_sim:.3f}"},
                         "resolver", f"alias {name} -> {best['id']}", source["at"])
            return best["id"]
        if band == "review":
            self.merge_queue.append({"candidate": eid, "existing": best["id"], "similarity": round(best_sim, 3)})
        return eid

    def relate(self, src: str, type: str, dst: str, source, context: str | None = None, attrs: dict | None = None,
               valid_from: str | None = None, valid_to: str | None = None, actor: str = "app") -> dict:
        source = check_source(source)
        with self._lock:
            rid = "rel_" + sha256_hex(f"{src}|{type}|{dst}|{context or ''}|{valid_from or ''}")[:16]
            payload = {"id": rid, "from": src, "type": type, "to": dst, "context": context, "attrs": attrs or {},
                       "validFrom": valid_from, "validTo": valid_to, "schemaVersion": 1, "source": source,
                       "createdAt": source["at"]}
            self._append("relate", payload, actor, f"{src} -{type}-> {dst}", source["at"])
            return self.state["relationships"][rid]

    def assert_fact(self, about: str, predicate: str, value, source, confidence: float = 0.5,
                    context: str | None = None, actor: str = "app") -> dict:
        """Record a fact. The same value already current for (about, predicate) is returned unchanged."""
        source = check_source(source)
        with self._lock:
            current = self.current_fact(about, predicate)
            if current and canonical_json(current["value"]) == canonical_json(value):
                return current
            fid = "fact_" + sha256_hex(f"{about}|{predicate}|{canonical_json(value)}|{source['at']}|"
                                       f"{source['kind']}|{source.get('url') or ''}")[:16]
            payload = {"id": fid, "about": about, "predicate": predicate, "value": value, "confidence": confidence,
                       "context": context, "source": source, "assertedAt": source["at"]}
            self._append("assertFact", payload, actor, f"{about} {predicate} = {canonical_json(value)}", source["at"])
            return self.state["facts"][fid]

    def record_decision(self, key: str, about: str, value: dict, depends_on: list[str], source,
                        actor: str = "app") -> dict:
        """An agent's decision and the facts it rests on. Recording the same key again replaces it."""
        source = check_source(source)
        with self._lock:
            missing = [f for f in depends_on if f not in self.state["facts"]]
            if missing:
                raise KeyError(f"unknown facts: {missing}")
            payload = {"key": key, "about": about, "value": value, "dependsOn": list(depends_on), "source": source,
                       "decidedAt": source["at"]}
            self._append("recordDecision", payload, actor, f"decide {key}", source["at"])
            return self.state["decisions"][key]

    def ingest(self, observations: list[dict], actor: str = "ingest") -> dict:
        """Add observations and the entities they mention. An observation already seen with the same
        content is skipped, so re-running a batch changes nothing."""
        with self._lock:
            before = self.state_shape_canonical()
            events_before = len(self._events)
            run_id = "run_" + sha256_hex(canonical_json([o["externalId"] for o in observations]))[:12]
            skipped = 0
            for obs in observations:
                source = check_source(obs.get("source"))
                checksum = sha256_hex(canonical_json({"externalId": obs["externalId"], "title": obs.get("title"),
                                                      "text": obs.get("text") or "", "at": obs["at"]}))
                seen = self.state["observations"].get(obs["externalId"])
                if seen and seen["checksum"] == checksum:
                    skipped += 1
                    continue
                oid = self.upsert_entity(type="observation", external_key={"system": source["kind"],
                                                                           "id": obs["externalId"]},
                                         attrs={"title": obs.get("title"), "at": obs["at"]}, source=source,
                                         actor=actor)["id"]
                mentioned = []
                for ent in obs.get("entities", []):
                    e = self.upsert_entity(type=ent["type"], name=ent["name"], source=source, actor=actor,
                                           resolve=False)
                    self.relate(src=oid, type="mentions", dst=e["id"], source=source, actor=actor)
                    mentioned.append(e["id"])
                self._append("observe", {"externalId": obs["externalId"], "entityId": oid, "checksum": checksum,
                                         "at": obs["at"], "entityIds": sorted(set(mentioned))},
                             actor, f"observe {obs['externalId']}", obs["at"])
            changed = self.state_shape_canonical() != before
            self._write_audit("ingest", actor, f"{run_id}: {len(observations) - skipped} processed, {skipped} skipped",
                              self.clock() if self.clock else observations[-1]["at"] if observations else "")
            self._save()
            return {"runId": run_id, "processed": len(observations) - skipped, "skippedUnchanged": skipped,
                    "clusters": len(self.state["stories"]), "eventsAppended": len(self._events) - events_before,
                    "changed": changed}

    # Reads

    def current_fact(self, about: str, predicate: str) -> dict | None:
        live = [f for f in self.state["facts"].values()
                if f["about"] == about and f["predicate"] == predicate and not f.get("supersededBy")]
        return max(live, key=lambda f: f["assertedAt"]) if live else None

    def decisions(self, status: str | None = None, about: str | None = None) -> list[dict]:
        out = [d for d in self.state["decisions"].values()
               if (status is None or d["status"] == status) and (about is None or d["about"] == about)]
        return sorted(out, key=lambda d: d["key"])

    def view(self, name: str):
        if name == "graph":
            return Graph(self)
        if name == "facts":
            return sorted(self.state["facts"].values(), key=lambda f: f["id"])
        raise ValueError(f"unknown view {name!r}")

    def events(self) -> list[dict]:
        return list(self._events)

    def audit(self) -> list[dict]:
        return list(self._audit)

    def state_shape_canonical(self) -> str:
        s = self.state
        return canonical_json({k: [s[k][i] for i in sorted(s[k])] for k in
                               ("entities", "relationships", "facts", "observations", "stories", "decisions")})
