# AI Trading System - AGENTS.md

## Goal

Build an adaptive trading system that:

- Selects best strategy dynamically
- Controls risk strictly
- Maximizes consistency, not just profit

## Core Principles

- Never trade without risk validation
- Never trust single strategy
- Always log every decision
- System must adapt to market regime

## Modules

### 1. Signal Layer

- Receives TradingView alerts
- Format: JSON `{strategy, signal, symbol, price}`

### 2. Meta Engine (Brain)

- Tracks last N trades per strategy
- Calculates score:
  `score = (win_rate * 0.4) + (profit_factor * 0.3) - (drawdown * 0.2)`
- Selects best strategy

### 3. Risk Engine (Guard)

- Max risk per trade: 1-2%
- Max daily loss: 3%
- Stop after 3 consecutive losses
- Block trade if unsafe

### 4. Execution Engine

- Executes only approved trades
- Adds SL/TP automatically
- Stores trade result

## Flow

Signal -> Meta Engine -> Risk Engine -> Execution -> Database -> App UI

## Data Tracking

- trades (entry, exit, pnl)
- strategy performance
- win rate
- drawdown

## Rules

- No trade without Meta approval
- No trade without Risk approval
- No direct execution bypassing system
- All trades must be logged

## Future Expansion

- AI learning layer
- Strategy auto-weight tuning
- User personalization
