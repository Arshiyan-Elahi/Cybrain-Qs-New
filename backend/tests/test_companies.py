def test_list_requires_authentication(client):
    assert client.get("/api/v1/companies").status_code == 401


def test_create_and_read(client, auth_headers, company):
    assert company["regulationIds"] == ["eu-gmp", "annex-11"]
    # Dates are serialised as ISO dates for the locale-formatting frontend.
    assert len(company["createdAt"]) == 10

    response = client.get(f"/api/v1/companies/{company['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Pharma GmbH"


def test_list_is_paged(client, auth_headers, company):
    response = client.get("/api/v1/companies", headers=auth_headers)
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["limit"] > 0 and body["offset"] == 0


def test_page_size_is_clamped(client, auth_headers, company):
    # A client cannot ask for an unbounded page.
    body = client.get("/api/v1/companies?limit=100000", headers=auth_headers).json()
    assert body["limit"] <= 200


def test_search_filters(client, auth_headers, company):
    assert client.get("/api/v1/companies?search=pharma", headers=auth_headers).json()["total"] == 1
    assert client.get("/api/v1/companies?search=zzzz", headers=auth_headers).json()["total"] == 0


def test_patch_updates_fields_and_regulations(client, auth_headers, company):
    response = client.patch(
        f"/api/v1/companies/{company['id']}",
        headers=auth_headers,
        json={"sopCount": 29, "regulationIds": ["eu-gmp"]},
    )
    assert response.status_code == 200
    assert response.json()["sopCount"] == 29
    assert response.json()["regulationIds"] == ["eu-gmp"]


def test_empty_name_rejected(client, auth_headers):
    response = client.post(
        "/api/v1/companies",
        headers=auth_headers,
        json={"name": "", "industryKey": "x", "locationKey": "y"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_delete(client, auth_headers, company):
    assert client.delete(f"/api/v1/companies/{company['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/companies/{company['id']}", headers=auth_headers).status_code == 404


class TestTenantIsolation:
    """The security property that matters most: companies never cross tenants."""

    def test_other_user_sees_nothing(self, client, company, user_factory):
        other = user_factory()
        assert client.get("/api/v1/companies", headers=other).json()["total"] == 0

    def test_other_user_cannot_read(self, client, company, user_factory):
        other = user_factory()
        # 404 rather than 403: a 403 would confirm the company exists.
        assert client.get(f"/api/v1/companies/{company['id']}", headers=other).status_code == 404

    def test_other_user_cannot_modify(self, client, company, user_factory):
        other = user_factory()
        assert (
            client.patch(
                f"/api/v1/companies/{company['id']}", headers=other, json={"sopCount": 999}
            ).status_code
            == 404
        )

    def test_other_user_cannot_delete(self, client, company, user_factory):
        other = user_factory()
        assert client.delete(f"/api/v1/companies/{company['id']}", headers=other).status_code == 404
