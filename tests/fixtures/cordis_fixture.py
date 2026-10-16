"""Synthetic CORDIS bulk zips for tests. All names are invented (Fixture ...); nothing here is a real company fact."""
import csv
import io
import zipfile

ORG_COLS = ["projectID", "projectAcronym", "vatNumber", "name", "shortName", "SME", "activityType", "city", "country", "role",
            "ecContribution", "netEcContribution", "totalCost"]
PROJ_COLS = ["id", "acronym", "title", "startDate", "endDate", "ecMaxContribution", "topics", "frameworkProgramme",
             "fundingScheme", "objective", "keywords"]


def org(pid, name, vat="", sme="true", act="PRC", country="FI", amount="1000", role="participant"):
    return {"projectID": pid, "projectAcronym": "X", "vatNumber": vat, "name": name, "shortName": "", "SME": sme,
            "activityType": act, "city": "Testville", "country": country, "role": role, "ecContribution": amount,
            "netEcContribution": amount, "totalCost": amount}


def proj(pid, title="Plain title", start="2025-06-01", objective="Plain objective", keywords="", fp="HORIZON"):
    return {"id": pid, "acronym": f"ACR{pid}", "title": title, "startDate": start, "endDate": "2028-05-31",
            "ecMaxContribution": "1", "topics": "T", "frameworkProgramme": fp, "fundingScheme": "HORIZON-IA",
            "objective": objective, "keywords": keywords}


def _csv(cols, rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, delimiter=";")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def make_zip(path, orgs, projects):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("organization.csv", _csv(ORG_COLS, orgs))
        z.writestr("project.csv", _csv(PROJ_COLS, projects))
    return path
