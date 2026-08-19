# Risk Management

## 1. Purpose

The Risk Management system is responsible for protecting the user's portfolio from excessive risk.

It acts as a safety layer between the AI decision system and trade execution.

The AI may generate trading opportunities, but it must never be able to bypass the defined risk rules.

The Risk Management system must evaluate every proposed trade before execution.

---

## 2. User Risk Profiles

The user can select a predefined risk profile.

### Low Risk

Maximum risk per trade:

1% of portfolio value.

### Medium Risk

Maximum risk per trade:

3% of portfolio value.

### High Risk

Maximum risk per trade:

5% of portfolio value.

The selected risk profile influences position sizing and whether a trade is acceptable.

The risk profile does not directly change the AI's underlying confidence score.

---

## 3. User-Configurable Risk Settings

The user should be able to configure risk settings from the application.

Planned settings include:

- Risk profile
- Maximum risk per trade
- Maximum daily loss
- Maximum portfolio exposure
- Maximum position size

The system should provide sensible defaults while allowing the user to customize supported limits.

---

## 4. Dynamic Position Sizing

The system will not use a fixed amount of capital for every trade.

Instead, the recommended position size will be calculated dynamically.

Position sizing may consider:

- Total portfolio value
- Available capital
- Selected risk profile
- Maximum risk per trade
- Entry price
- Stop-loss price
- Market volatility
- AI confidence
- Expected return
- Existing portfolio exposure
- Existing positions

The AI should recommend a position size that remains within the user's risk limits.

Example:

Portfolio:

$10,000

Risk profile:

Medium

AI opportunity:

NVDA — BUY

Entry:

$180

Stop-loss:

$177

The system calculates the recommended position size based on the allowed risk and stop-loss distance.

---

## 5. Maximum Position Size

A user-configurable maximum position size will be supported.

The system will also maintain a hard maximum position-size safety limit.

The AI cannot exceed the system-level hard limit even if the user configuration allows a larger position.

The lower of the applicable limits must always be respected.

---

## 6. Maximum Portfolio Exposure

The system will monitor the percentage of the portfolio currently invested.

Example:

Portfolio:

$10,000

Current positions:

NVDA — $2,000

AAPL — $2,000

MSFT — $2,000

Total exposure:

60%

The system must evaluate the user's maximum allowed portfolio exposure before approving a new trade.

The user can configure the desired exposure limit.

A system-level hard maximum will also exist.

The AI cannot exceed the hard maximum.

---

## 7. Daily Loss Limit

The user can define a maximum daily loss limit.

Example:

Portfolio:

$10,000

Daily loss limit:

5%

Maximum daily loss:

$500

If the portfolio reaches the configured daily loss limit:

1. Automatic trading is stopped.
2. The user receives a mandatory notification.
3. The AI continues monitoring the market.
4. The AI may continue generating trade proposals.
5. New trades require explicit manual approval.
6. Automatic trading remains disabled until the next trading day.

---

## 8. Trading Lock After Daily Loss Limit

When the daily loss limit is reached, the system enters a protected state.

Example:

```text
AUTO TRADING: DISABLED

Reason:
Daily loss limit reached.

AI ANALYSIS:
ACTIVE

MANUAL TRADING:
AVAILABLE
