"""Catalog migration: products, monitored_urls

Revision ID: 0002
Revises: dc416f4b417a
Create Date: 2026-11-14 00:00:00

Crea las tablas de los 2 modelos ORM del módulo catalog:
- `Product`       → tabla `products`        (backend/src/modules/catalog/models.py)
- `MonitoredURL`  → tabla `monitored_urls`  (backend/src/modules/catalog/models.py)
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002"
down_revision = "dc416f4b417a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("brand", sa.String(length=100), nullable=False),
        sa.Column("main_category", sa.String(length=100), nullable=False),
        sa.Column("sub_category", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "sku", name="uq_products_client_sku"),
    )
    op.create_index(op.f("ix_products_client_id"), "products", ["client_id"], unique=False)
    op.create_table(
        "monitored_urls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("retailer_name", sa.String(length=50), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_scraped_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_monitored_urls_product_id"), "monitored_urls", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_monitored_urls_product_id"), table_name="monitored_urls")
    op.drop_table("monitored_urls")
    op.drop_index(op.f("ix_products_client_id"), table_name="products")
    op.drop_table("products")
