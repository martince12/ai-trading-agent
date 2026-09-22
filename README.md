# AI Trading Agent

Autonomous AI-powered stock trading research and paper-trading system.

## Status

Early development

## Goal

See [Project Goal](docs/01-project/project-goal.md).

## Initial Market

US Stocks

## Initial Mode

Paper Trading

## Documentation

Project documentation is located in the `docs/` directory.

## Market data

The Python service includes a Massive daily OHLCV collector, validation, PostgreSQL
storage, a periodic worker and a FastAPI read API. See the
[setup, API and validation guide](docs/02-market-data.md).
