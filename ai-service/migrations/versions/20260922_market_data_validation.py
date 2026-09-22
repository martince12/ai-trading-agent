"""Add OHLCV integrity constraints and ingestion audit history.

Revision ID: 20260922_market_data
Revises: 13ac5eb350db
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_market_data"
down_revision = "13ac5eb350db"
branch_labels = None
depends_on = None


def upgrade():
    # Existing invalid rows deliberately fail migration rather than being silently deleted.
    with op.batch_alter_table("market_candles") as batch:
        batch.create_check_constraint("ck_market_candle_prices", "open > 0 AND open < 1e308 AND high > 0 AND high < 1e308 AND low > 0 AND low < 1e308 AND close > 0 AND close < 1e308")
        batch.create_check_constraint("ck_market_candle_volume", "volume >= 0 AND volume < 1e308")
        batch.create_check_constraint("ck_market_candle_ohlc", "low <= open AND low <= close AND high >= open AND high >= close")
    op.create_table(
        "market_data_ingestion_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("fetched", sa.Integer(), nullable=False),
        sa.Column("saved", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(300), nullable=True),
    )
    op.create_index("ix_market_data_ingestion_runs_symbol", "market_data_ingestion_runs", ["symbol"])


def downgrade():
    op.drop_table("market_data_ingestion_runs")
    with op.batch_alter_table("market_candles") as batch:
        for name in ("ck_market_candle_prices", "ck_market_candle_volume", "ck_market_candle_ohlc"):
            batch.drop_constraint(name, type_="check")
