def test_cors_preflight_allows_business_origin(client):
    response = client.options(
        "/api/v1/widget/bootstrap",
        headers={
            "Origin": "https://business.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers
