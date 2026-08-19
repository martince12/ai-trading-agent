# Trading Strategy & Interaction Model

## Trading Horizon

The initial system will use a hybrid short-term trading approach.

Primary:
- Several hours to approximately 1–2 trading days

Secondary:
- Shorter intraday opportunities

The system prioritizes quality over trading frequency.
It is allowed to produce no trade when no sufficiently strong opportunity exists.

## Signal Threshold

The initial target threshold is 70%+ model confidence.

This threshold is experimental and must be validated and calibrated through backtesting and paper trading.

## User Interaction

The initial version will use manual approval.

The AI will analyze the market and generate a trade proposal.
The user must approve or reject the proposal before the paper trade is executed.

Future versions may support:
- Manual mode
- Semi-automatic mode
- Fully automatic mode

## Notifications

When a sufficiently strong opportunity is detected, the user receives a notification.

The notification provides a concise summary.

Example:

NVDA — BUY
Confidence: 82%
Expected holding: 6–24h

The user can open the notification to view the complete analysis.

## Trade Analysis

The detailed trade proposal should include:

- Asset
- BUY / SELL / HOLD
- Confidence
- Entry price
- Target price
- Stop-loss price
- Expected holding period
- Expected profit
- Expected loss
- Profit percentage
- Loss percentage
- Risk/reward ratio
- Relevant market indicators
- Relevant news/events
- AI reasoning
- Risk assessment

The system should calculate these values automatically so the user does not need to perform manual calculations.

## No-Trade Decision

The AI is not required to trade.

If no opportunity satisfies the defined conditions, the system should return:

NO TRADE

This is considered a valid and expected system decision.
