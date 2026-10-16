-- Derived first-traction facts per company. Written only by radar/adapters/tax_registers.py. Never a signal.
CREATE TABLE IF NOT EXISTS company_traction (
  company_key          TEXT PRIMARY KEY REFERENCES companies(company_key),
  founded              TEXT,      -- ISO date copied from the register at check time
  first_hire_date      TEXT,      -- employer register (7) entry date, NULL when the register shows none
  months_to_first_hire INTEGER,   -- whole calendar months from founded to first_hire_date, NULL when either is unknown
  checked_at           TEXT NOT NULL
);
