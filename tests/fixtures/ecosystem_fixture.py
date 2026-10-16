"""Test-only builder: a SYNTHETIC imitation of data/declared/ecosystem/blue_economy_fi.sqlite plus a radar database. Never loaded by the app."""
from __future__ import annotations

import csv
import sqlite3

from radar import db, emit

SCHEMA = """
CREATE TABLE entity (id TEXT PRIMARY KEY, name TEXT, entity_type TEXT, side TEXT, business_id TEXT, country TEXT, city TEXT, region TEXT,
  founded INTEGER, website TEXT, stage TEXT, confidence TEXT, last_verified TEXT, status TEXT);
CREATE TABLE source (id INTEGER PRIMARY KEY, entity_id TEXT, url TEXT);
CREATE TABLE match (id INTEGER PRIMARY KEY, supply_id TEXT, supply_name TEXT, target_id TEXT, target_name TEXT, target_side TEXT, target_type TEXT, score REAL, why TEXT);
CREATE TABLE readiness (entity_id TEXT PRIMARY KEY, name TEXT, oi_score INTEGER, oir_score INTEGER, oir_evidence TEXT, trl INTEGER,
  customer_evidence TEXT, br_score INTEGER, br_evidence TEXT, br_missing TEXT, ir_score INTEGER, ir_evidence TEXT, ir_missing TEXT, sources TEXT,
  confidence TEXT, last_verified TEXT);
CREATE TABLE event (id INTEGER PRIMARY KEY, date TEXT, company TEXT, entity_id TEXT, event_type TEXT, amount_eur REAL, counterparty TEXT, summary TEXT,
  sources TEXT, date_precision TEXT, confidence TEXT);
CREATE TABLE job_signal (id INTEGER PRIMARY KEY, entity_id TEXT, role TEXT, url TEXT, date TEXT, language_req TEXT);
"""
PRH = "https://example.test/synthetic-prh?businessId="


def build_dataset(path):
    c = sqlite3.connect(str(path))
    c.executescript(SCHEMA)
    ent = [
        ("S1", "Fixture Oy", "startup", "supply", "9100001-1", None, "https://fixture.example.test", "seed", "medium", "active"),
        ("S2", "Fixture Two Oy", "startup", "supply", "9100002-2", None, "https://two.example.test", "seed", "low", "active"),
        ("S3", "Fixture Gone Oy", "startup", "supply", None, None, "https://gone.example.test", "seed", "low", "defunct"),
        ("S4", "Fixture Domain Ab", "startup", "supply", None, None, "https://domain.example.test/en", "seed", "high", "active"),
        ("C1", "Fixture Capital", "investor_vc", "capital", None, None, "https://cap1.example.test", None, "high", "active"),
        ("C2", "Fixture Angels", "investor_angel", "capital", None, None, "https://cap2.example.test", None, "low", "active"),
        ("C3", "Fixture Fund", "public_funder", "capital", None, None, None, None, "medium", "active"),
        ("C4", "Fixture Closed Fund", "investor_vc", "capital", None, None, "https://cap4.example.test", None, "high", "defunct"),
        ("D1", "Fixture Buyer", "corporate", "demand", None, None, "https://buyer.example.test", None, "medium", "active"),
    ]
    c.executemany("INSERT INTO entity (id,name,entity_type,side,business_id,country,website,stage,confidence,status,last_verified) VALUES (?,?,?,?,?,?,?,?,?,?,'2026-10-16')", ent)
    c.execute("INSERT INTO source (entity_id,url) VALUES ('C3','https://fund.example.test/about')")
    m = [("S1", "C1", "capital", "investor_vc", 80.0, "caps ['C1']; kw ['x']; stage 1.0"),
         ("S1", "C2", "capital", "investor_angel", 90.0, "caps ['C1']; kw []; stage 0.5"),
         ("S1", "C3", "capital", "public_funder", 70.0, "caps ['C1']; kw []; stage 1.0"),
         ("S1", "D1", "demand", "corporate", 60.0, "caps ['C1']; kw ['y']; stage 0.5"),
         ("S1", "C4", "capital", "investor_vc", 99.0, "closed fund must never be listed"),
         ("S3", "C1", "capital", "investor_vc", 50.0, "defunct supplier")]
    for i, (s, t, side, ty, sc, why) in enumerate(m, 1):
        c.execute("INSERT INTO match VALUES (?,?,?,?,?,?,?,?,?)", (i, s, s, t, t, side, ty, sc, why))
    c.execute("INSERT INTO readiness (entity_id,name,trl,br_score,br_evidence,br_missing,ir_score,ir_evidence,ir_missing,oir_score,sources,confidence,last_verified) VALUES "
              "('S1','Fixture Oy',6,3,'FY2025 revenue stated - https://rev.example.test/fixture; chair Some Person named; https://www.linkedin.com/in/some-person-1','a; b',2,"
              "'angel round stated','c',1,'https://rev.example.test/fixture https://www.linkedin.com/in/some-person-1','medium','2026-10-16')")
    ev = [("2025-11-20", "S1", "first_customer_or_pilot_named", None, "Fixture pilot named by a founder Some Person", "https://pilot.example.test/a", "day", "high"),
          ("2025-10", "S1", "exhibitor_or_demo", None, "month only", "https://expo.example.test/a", "month", "medium"),
          ("2024", "S1", "award_or_pitch_win", None, "year only", "https://award.example.test/a", "year", "low"),
          ("2023-05-05", "S1", "founding", None, "founding is not a signal", "https://reg.example.test/a", "day", "high"),
          ("2026-02-09", "S1", "accelerator_or_programme_entry", None, "named in the Nordic Blue 2026 batch", "https://batch.example.test/a", "day", "high"),
          ("", "S1", "product_launch", None, "no date", "https://launch.example.test/a", "none", "high"),
          ("2025-12-01", "S1", "funding_round", 500000.0, "round", "https://round.example.test/a", "day", "medium"),
          ("2025-12-02", "S1", "contract", None, "contract", "https://contract.example.test/a", "day", "medium")]
    for i, (d, e, ty, amt, summ, src, prec, conf) in enumerate(ev, 1):
        c.execute("INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)", (i, d, e, e, ty, amt, None, summ, src, prec, conf))
    c.execute("INSERT INTO job_signal (entity_id,role,url,date) VALUES ('S1','Open application only','https://jobs.example.test/a','2026-10')")
    c.execute("INSERT INTO job_signal (entity_id,role,url,date) VALUES ('S1','Welder','https://jobs.example.test/b','2026-10')")
    c.commit()
    c.close()


def build_radar(path):
    conn = db.connect(path)
    emit.upsert_company(conn, company_key="9100001-1", name="Fixture Oy", y_tunnus="9100001-1", country="FI", founded="2024-03-01",
                        group_tag="cohort", source_url=PRH + "9100001-1")
    emit.upsert_company(conn, company_key="name:fixture-domain", name="Domain Holder Fixture", website="https://domain.example.test/", group_tag="portfolio",
                        source_url="https://example.test/declared")
    emit.upsert_company(conn, company_key="name:lonely", name="Lonely Fixture", group_tag="cohort", source_url="https://example.test/declared")
    emit.emit_signal(conn, company_key="9100001-1", signal_type="register_entry", date="2024-03-01", source_url=PRH + "9100001-1",
                     confidence="high", adapter="prh", detail="Synthetic registration.")
    conn.commit()
    return conn


def write_programmes(path, rows):
    cols = ["name", "type", "stage_window", "TRL_window_if_stated", "geography", "next_deadline", "amount_eur", "eligibility_summary", "url", "source_url", "note"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({**{c: "" for c in cols}, **r})
