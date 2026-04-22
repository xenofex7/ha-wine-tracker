"""
Tests for the Advanced Filter preset CRUD endpoints.
"""
import json


def _create(client, name, conditions=None):
    if conditions is None:
        conditions = {"rules": [{"field": "type", "op": "in", "value": ["Rotwein"]}]}
    return client.post(
        "/api/filter-presets",
        data=json.dumps({"name": name, "conditions": conditions}),
        content_type="application/json",
    )


class TestListAndCreate:
    def test_list_empty(self, client):
        resp = client.get("/api/filter-presets")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        assert body["presets"] == []

    def test_create_minimal(self, client):
        resp = _create(client, "Reds")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["ok"] is True
        preset = body["preset"]
        assert preset["name"] == "Reds"
        assert preset["conditions"]["rules"][0]["field"] == "type"
        assert "id" in preset
        assert "created" in preset
        assert "updated" in preset

    def test_list_returns_created(self, client):
        _create(client, "Reds")
        _create(client, "Whites", {"rules": [{"field": "type", "op": "in", "value": ["Weisswein"]}]})
        resp = client.get("/api/filter-presets")
        body = resp.get_json()
        assert len(body["presets"]) == 2

    def test_list_alphabetical(self, client):
        _create(client, "Zebra")
        _create(client, "Alpha")
        _create(client, "Mango")
        resp = client.get("/api/filter-presets")
        names = [p["name"] for p in resp.get_json()["presets"]]
        assert names == ["Alpha", "Mango", "Zebra"]

    def test_list_alphabetical_case_insensitive(self, client):
        _create(client, "beta")
        _create(client, "Alpha")
        resp = client.get("/api/filter-presets")
        names = [p["name"] for p in resp.get_json()["presets"]]
        assert names == ["Alpha", "beta"]

    def test_reject_empty_name(self, client):
        resp = _create(client, "")
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "name_required"

    def test_reject_whitespace_name(self, client):
        resp = _create(client, "   ")
        assert resp.status_code == 400

    def test_reject_missing_conditions(self, client):
        resp = client.post(
            "/api/filter-presets",
            data=json.dumps({"name": "X"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"] == "conditions_required"

    def test_reject_duplicate_name(self, client):
        _create(client, "Reds")
        resp = _create(client, "Reds")
        assert resp.status_code == 409
        assert resp.get_json()["error"] == "name_exists"

    def test_conditions_roundtrip_complex(self, client):
        conds = {
            "rules": [
                {"field": "rating", "op": "between", "value": [4, 5]},
                {"field": "type", "op": "in", "value": ["Rotwein", "Weisswein"]},
                {"field": "notes", "op": "contains", "value": "bordeaux"},
            ]
        }
        resp = _create(client, "Complex", conds)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["preset"]["conditions"] == conds


class TestUpdate:
    def test_update_name_and_conditions(self, client):
        r = _create(client, "Reds")
        pid = r.get_json()["preset"]["id"]

        new_conds = {"rules": [{"field": "year", "op": "gte", "value": 2020}]}
        resp = client.put(
            f"/api/filter-presets/{pid}",
            data=json.dumps({"name": "Old Reds", "conditions": new_conds}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["preset"]["name"] == "Old Reds"
        assert body["preset"]["conditions"] == new_conds

    def test_update_not_found(self, client):
        resp = client.put(
            "/api/filter-presets/999",
            data=json.dumps({"name": "X", "conditions": {}}),
            content_type="application/json",
        )
        assert resp.status_code == 404

    def test_update_to_duplicate_name(self, client):
        _create(client, "Reds")
        r = _create(client, "Whites")
        pid = r.get_json()["preset"]["id"]
        resp = client.put(
            f"/api/filter-presets/{pid}",
            data=json.dumps({"name": "Reds", "conditions": {"rules": []}}),
            content_type="application/json",
        )
        assert resp.status_code == 409

    def test_update_same_name_no_conflict(self, client):
        r = _create(client, "Reds")
        pid = r.get_json()["preset"]["id"]
        resp = client.put(
            f"/api/filter-presets/{pid}",
            data=json.dumps({"name": "Reds", "conditions": {"rules": []}}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_update_empty_name(self, client):
        r = _create(client, "Reds")
        pid = r.get_json()["preset"]["id"]
        resp = client.put(
            f"/api/filter-presets/{pid}",
            data=json.dumps({"name": "", "conditions": {"rules": []}}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestDelete:
    def test_delete(self, client):
        r = _create(client, "Reds")
        pid = r.get_json()["preset"]["id"]
        resp = client.delete(f"/api/filter-presets/{pid}")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True

        listing = client.get("/api/filter-presets").get_json()
        assert listing["presets"] == []

    def test_delete_not_found(self, client):
        resp = client.delete("/api/filter-presets/999")
        assert resp.status_code == 404
