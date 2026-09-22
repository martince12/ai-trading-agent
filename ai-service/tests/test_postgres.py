"""Opt-in PostgreSQL verification in a temporary, transaction-scoped schema."""
import os
from pathlib import Path
import unittest
from uuid import uuid4

from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from test_market_data import Base, MarketDataRepository, candle, START, END


@unittest.skipUnless(os.getenv("MARKET_DATA_TEST_POSTGRES") == "1", "Set MARKET_DATA_TEST_POSTGRES=1 for local PostgreSQL verification")
class PostgreSQLTests(unittest.TestCase):
    def test_exact_upsert_counts_and_roundtrip(self):
        url = os.getenv("MARKET_DATA_TEST_DATABASE_URL") or dotenv_values(Path(__file__).parents[1] / ".env").get("DATABASE_URL")
        self.assertTrue(url, "A PostgreSQL test database URL is required")
        engine = create_engine(url)
        self.assertEqual(engine.dialect.name, "postgresql")
        try:
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    schema = "market_test_" + uuid4().hex
                    connection.execute(CreateSchema(schema))
                    connection = connection.execution_options(schema_translate_map={None: schema})
                    Base.metadata.create_all(connection)
                    with Session(connection, join_transaction_mode="create_savepoint") as session:
                        repository = MarketDataRepository()
                        self.assertEqual(repository.save_candles(session, [candle()]), 1)
                        session.commit()
                        self.assertEqual(repository.save_candles(session, [candle()]), 0)
                        self.assertEqual(repository.save_candles(session, [candle(close=75)]), 1)
                        session.commit()
                        self.assertEqual(repository.get_candles(session, "AAPL", START, END), [candle(close=75)])
                finally:
                    # Includes schema creation: no test rows or tables survive.
                    transaction.rollback()
        finally:
            engine.dispose()
