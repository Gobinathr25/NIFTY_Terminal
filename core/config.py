"""
Global configuration and constants.
PAPER_MODE = True disables ALL real order placement.
"""

import pytz

# ─── PAPER TRADING GUARD ─────────────────────────────────────────────────────
PAPER_MODE: bool = True          # Never set False in production without review

# ─── TRADING SCHEDULE (IST) ──────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN_TIME     = "09:15"
STRATEGY_START_TIME  = "09:20"
NO_NEW_TRADES_TIME   = "14:45"
FORCE_CLOSE_TIME     = "15:10"
EOD_REPORT_TIME      = "15:20"

# ─── STRATEGY PARAMETERS ─────────────────────────────────────────────────────
SUPERTREND_PERIOD    = 10
SUPERTREND_MULT      = 2.0
VWAP_PERIOD          = "1D"

# Strangle delta targets
CE_DELTA_TARGET      = 0.22      # sell ~20-25 delta CE
PE_DELTA_TARGET      = -0.22     # sell ~20-25 delta PE
HEDGE_DELTA_TARGET   = 0.10      # buy 0.10 delta CE + PE hedge for margin benefit

# Expiry version (after 09:45)
EXPIRY_OTM_OFFSET    = 100       # ATM + 100 for OTM

# ─── RISK PARAMETERS ─────────────────────────────────────────────────────────
MAX_RISK_PCT_DAY     = 2.0       # 2% capital max per day
MAX_TRADES_PER_DAY   = 2         # max 2 strategy entries per day
MAX_ADJUSTMENTS      = 3         # max gamma adjustments before close

# Gamma Defence Thresholds
GAMMA_L1_SPOT_MOVE   = 0.006     # 0.6% spot move triggers L1
GAMMA_L1_PREMIUM_PCT = 0.40      # 40% premium rise triggers L1
GAMMA_L2_DELTA_LIMIT = 35        # tested leg delta > 35 triggers L2
GAMMA_L3_SPOT_MOVE   = 0.012     # 1.2% move
GAMMA_L3_TIME_WINDOW = 45        # within 45 minutes

# Expiry version P&L targets
EXPIRY_TARGET_PCT    = 0.30      # 30% of premium collected
EXPIRY_STOP_MULT     = 1.5       # 1.5x premium collected

# ─── FYERS ────────────────────────────────────────────────────────────────────
FYERS_BASE_URL       = "https://api-t1.fyers.in/api/v3"
NIFTY_INDEX_SYMBOL   = "NSE:NIFTY50-INDEX"
NIFTY_OPT_PREFIX     = "NSE:NIFTY"

# ─── DATABASE ────────────────────────────────────────────────────────────────
DB_PATH              = "paper_trading.db"

# ─── LOGGING ─────────────────────────────────────────────────────────────────
LOG_LEVEL            = "INFO"
LOG_FILE             = "terminal.log"
