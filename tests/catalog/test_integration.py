"""Tests de integración del módulo CATALOG: endpoints /catalog/*.

Criterios de aceptación cubiertos:
- Alta de producto en el catálogo maestro del tenant (client_id del JWT).
- SKU duplicado dentro del tenant → 409.
- Association de URL a producto del propio tenant → 201.
- URL contra producto de OTRO tenant → 404 (aislamiento multi-tenant).
- RBAC: `viewer` lee (200) pero no escribe (403).
- Paginado y filtros del listado de productos.
"""

from utils.factories import create_operational_user, create_product

BASE = "/api/v1"
PRODUCT_PAYLOAD = {
    "sku": "SKU-TEST-001",
    "name": "Heladera Gafa 450L",
    "brand": "Gafa",
    "main_category": "electrodomesticos",
    "sub_category": "heladeras",
}


# ---------------------------------------------------------------------------
# Catálogo maestro: alta y unicidad de SKU
# ---------------------------------------------------------------------------
def test_admin_creates_product(client, verified_admin):
    """El admin da de alta un producto; el client_id se inyecta del JWT."""
    admin = verified_admin("catadmin@corp.com", "Pwd12345!", "Corp Cat")

    product = create_product(client, admin["headers"], PRODUCT_PAYLOAD)

    assert product["sku"] == PRODUCT_PAYLOAD["sku"]
    assert product["name"] == PRODUCT_PAYLOAD["name"]
    assert product["is_active"] is True
    assert product["created_at"] is not None


def test_duplicate_sku_in_tenant_conflicts(client, verified_admin):
    """El mismo SKU no puede repetirse dentro del tenant (409)."""
    admin = verified_admin("catsku@corp.com", "Pwd12345!", "Corp SKU")

    create_product(client, admin["headers"], PRODUCT_PAYLOAD)

    response = client.post(
        f"{BASE}/catalog/products",
        json={**PRODUCT_PAYLOAD, "name": "Otro nombre"},
        headers=admin["headers"],
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Enlaces de monitoreo
# ---------------------------------------------------------------------------
def test_analyst_links_url_to_own_product(client, verified_admin, dev_token):
    """El analyst asocia un enlace de retailer a un producto de SU tenant."""
    admin = verified_admin("caturl@corp.com", "Pwd12345!", "Corp URL")
    analyst = create_operational_user(
        client, admin, "caturlanalyst@corp.com", "analyst", dev_token
    )

    product = create_product(client, analyst["headers"], PRODUCT_PAYLOAD)

    response = client.post(
        f"{BASE}/catalog/urls",
        json={
            "product_id": product["id"],
            "retailer_name": "fravega",
            "url": "https://www.fravega.com/p/heladera-gafa-450",
        },
        headers=analyst["headers"],
    )
    assert response.status_code == 201
    url = response.json()
    assert url["product_id"] == product["id"]
    assert url["retailer_name"] == "fravega"
    assert url["is_active"] is True
    assert url["last_scraped_at"] is None

    listing = client.get(
        f"{BASE}/catalog/urls/{product['id']}", headers=analyst["headers"]
    )
    assert listing.status_code == 200
    assert [u["id"] for u in listing.json()] == [url["id"]]


def test_url_against_foreign_product_not_found(client, verified_admin):
    """Un tenant NO puede vincular/consultar URLs de productos ajenos (404)."""
    admin_a = verified_admin("cata@corp.com", "Pwd12345!", "Corp A")
    admin_b = verified_admin("catb@corp.com", "Pwd12345!", "Corp B")

    foreign_product = create_product(client, admin_a["headers"], PRODUCT_PAYLOAD)

    link = client.post(
        f"{BASE}/catalog/urls",
        json={
            "product_id": foreign_product["id"],
            "retailer_name": "cetrogar",
            "url": "https://www.cetrogar.com/p/xyz",
        },
        headers=admin_b["headers"],
    )
    assert link.status_code == 404

    listing = client.get(
        f"{BASE}/catalog/urls/{foreign_product['id']}", headers=admin_b["headers"]
    )
    assert listing.status_code == 404


# ---------------------------------------------------------------------------
# RBAC: viewer solo lectura
# ---------------------------------------------------------------------------
def test_viewer_has_read_only_access(client, verified_admin, dev_token):
    """El viewer consulta el catálogo (200) pero no puede escribir (403)."""
    admin = verified_admin("catview@corp.com", "Pwd12345!", "Corp View")
    viewer = create_operational_user(
        client, admin, "catviewer@corp.com", "viewer", dev_token
    )

    create_product(client, admin["headers"], PRODUCT_PAYLOAD)

    listing = client.get(f"{BASE}/catalog/products", headers=viewer["headers"])
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    write = client.post(
        f"{BASE}/catalog/products", json=PRODUCT_PAYLOAD, headers=viewer["headers"]
    )
    assert write.status_code == 403


# ---------------------------------------------------------------------------
# Listado: paginado y filtros
# ---------------------------------------------------------------------------
def test_list_products_pagination_and_filters(client, verified_admin):
    """El listado pagina (page/page_size) y filtra por categoría y estado."""
    admin = verified_admin("catlist@corp.com", "Pwd12345!", "Corp List")

    create_product(client, admin["headers"], PRODUCT_PAYLOAD, sku="SKU-L1", main_category="audio")
    create_product(client, admin["headers"], PRODUCT_PAYLOAD, sku="SKU-L2", main_category="audio")
    create_product(client, admin["headers"], PRODUCT_PAYLOAD, sku="SKU-L3", main_category="tv")

    page1 = client.get(
        f"{BASE}/catalog/products",
        params={"page": 1, "page_size": 2},
        headers=admin["headers"],
    )
    assert page1.status_code == 200
    body = page1.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2

    audio = client.get(
        f"{BASE}/catalog/products",
        params={"main_category": "audio"},
        headers=admin["headers"],
    )
    assert audio.status_code == 200
    assert audio.json()["total"] == 2

    inactive = client.get(
        f"{BASE}/catalog/products",
        params={"is_active": False},
        headers=admin["headers"],
    )
    assert inactive.status_code == 200
    assert inactive.json()["total"] == 0
