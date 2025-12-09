def test_cache_stats_admin(admin_client):
    resp = admin_client.get("/api/admin/cache/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_cache_flush_admin(admin_client):
    resp = admin_client.post("/api/admin/cache/flush")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
