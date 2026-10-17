-- Wide intake (jx28): the register facts the intake rule needs and the companies table does not carry. Written by radar/adapters/prh_intake.py.
CREATE TABLE IF NOT EXISTS intake_profile (
  company_key  TEXT PRIMARY KEY REFERENCES companies(company_key),
  form_code    TEXT,      -- PRH company form code of the current form, NULL when the register states none
  form_desc    TEXT,
  registered   TEXT,      -- ISO date of the company's registration (business id registration date)
  checked_at   TEXT NOT NULL
);
