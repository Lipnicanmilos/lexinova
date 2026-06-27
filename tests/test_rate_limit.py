"""Rate limiting — registrácia má limit 5/hodina (per IP)."""


def test_register_rate_limited_after_5(rate_limited_client):
    c = rate_limited_client
    statuses = [
        c.post("/api/v1/register", json={"email": f"rl{i}@example.com", "password": "Abcdef12"}).status_code
        for i in range(7)
    ]
    # prvých 5 prejde, ďalšie sú zablokované (429)
    assert statuses[:5] == [200, 200, 200, 200, 200]
    assert 429 in statuses[5:]
