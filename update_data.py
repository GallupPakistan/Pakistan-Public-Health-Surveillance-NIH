"""
IDSR bulletin -> main data updater (no PDFs are stored).

What it does every time it runs
  1. Reads the NIH bulletin page and lists every "Week N Bulletin (YYYY)" PDF.
  2. Finds weeks that are NOT yet in data/core.parquet.
  3. Downloads each missing PDF straight into memory (nothing is saved to disk),
     extracts the tables, checks the numbers, and appends them to
        data/core.parquet       (district-level cases: Tables 2, 3, 4)
        data/reporting.parquet  (district reporting compliance: Table 6)
  4. If nothing new is published it prints:  No data found
  5. A week already in the file is never added twice.

Usage
    python update_data.py                       # normal daily run
    python update_data.py --dry-run             # show what would be added, change nothing
    python update_data.py --only 2025-52        # process one week only
    python update_data.py --backfill-reporting  # also fill reporting.parquet for old weeks
                                                #   that are in core.parquet but not in reporting
    python update_data.py --accept-mismatch     # LOCAL USE ONLY, never in the workflow: saves a week whose totals do not add up
    python update_data.py --retry-skipped       # retry weeks that were quarantined earlier
    python update_data.py --strict-exit         # exit with code 1 if any week was skipped

Weeks that cannot be read (layout change, totals that do not add up, ...) are written to
data/skipped_weeks.json with the reason and are NOT retried for RETRY_AFTER_DAYS days, so one
bad bulletin no longer makes every daily run slow and red.  They are reported as a warning.
"""
import argparse
import io
import json
import os
import re
import shutil
import sys
import time
from datetime import date
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import pandas as pd
import pdfplumber
import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://www.nih.org.pk/phb/weekly-bulletin"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IDSR-bulletin-bot/1.0)"}
RETRY_AFTER_DAYS = 7          # a quarantined week is tried again after this many days
SKIP_FILE = "skipped_weeks.json"
TITLE_RE = re.compile(r"Week\s*(\d+)\s*Bulletin\s*\((\d{4})\)", re.I)

# ----------------------------------------------------------------------------
# Same naming / category rules as prepare_data.py so new rows match old rows
# ----------------------------------------------------------------------------
DISEASE_FULL = {
    "adnoncholera": "AD (Acute Diarrhea, Non-Cholera)",
    "alri5years": "ALRI (Acute Lower Respiratory Infection, <5 years)",
    "avhae": "AVH (Acute Viral Hepatitis, A & E)",
    "awdscholera": "AWD (Acute Watery Diarrhea, Suspected Cholera)",
    "bdiarrhea": "B. Diarrhea (Bloody Diarrhea)",
    "cl": "CL (Cutaneous Leishmaniasis)",
    "dengue": "Dengue",
    "dogbite": "Dog/Animal Bite (Rabies)",
    "animaldogbite": "Dog/Animal Bite (Rabies)",     # newer bulletins (2026) write the heading this way
    "animalbite": "Dog/Animal Bite (Rabies)",
    "ili": "ILI (Influenza-like Illness)",
    "malaria": "Malaria",
    "measles": "Measles",
    "sari": "SARI (Severe Acute Respiratory Infection)",
    "tb": "TB (Tuberculosis)",
    "typhoid": "Typhoid",
    "mumps": "Mumps",
    "pertussis": "Pertussis",
    "chikungunya": "Chikungunya",
    "vhbcd": "VH (Viral Hepatitis B, C & D)",
}
DISEASE_CATEGORY = {
    "AD (Acute Diarrhea, Non-Cholera)": "Waterborne",
    "AWD (Acute Watery Diarrhea, Suspected Cholera)": "Waterborne",
    "B. Diarrhea (Bloody Diarrhea)": "Waterborne",
    "Typhoid": "Waterborne",
    "AVH (Acute Viral Hepatitis, A & E)": "Waterborne",
    "VH (Viral Hepatitis B, C & D)": "Bloodborne",
    "ALRI (Acute Lower Respiratory Infection, <5 years)": "Respiratory",
    "ILI (Influenza-like Illness)": "Respiratory",
    "SARI (Severe Acute Respiratory Infection)": "Respiratory",
    "TB (Tuberculosis)": "Respiratory",
    "Measles": "Respiratory",
    "Malaria": "Vector-borne",
    "Dengue": "Vector-borne",
    "CL (Cutaneous Leishmaniasis)": "Vector-borne",
    "Dog/Animal Bite (Rabies)": "Zoonotic",
}

# PDF spelling -> spelling used in your existing files (key = letters/digits only, lower case)
ALIAS_CORE = {
    "kamber": "Kamber Shahdadkot", "naushero feroze": "Naushahro Feroze",
    "kachhibolan": "Kachhi", "lasbella": "Lasbela", "naseerabad": "Nasirabad",
    "killasaifullah": "Qila Saifullah", "killaabdullah": "Qilla Abdullah",
    "lckurram": "Kurram", "lowercentralkurram": "Kurram",
    "kechturbat": "Kech", "chagi": "Chagai",
}
ALIAS_REP = {
    "jhelumvelley": "Jhelum Valley", "kambershadadkot": "Kamber Shahdadkot",
    "kachhibolan": "Kachhi", "lasbella": "Lasbela",
    "killasaifullah": "Qila Saifullah", "killaabdullah": "Qilla Abdullah",
    "lowercentralkurram": "L & C Kurram", "lckurram": "L & C Kurram",
    "ict": "Islamabad Capital Territory", "kechturbat": "Kech", "chagi": "Chagai",
}
ALIAS_REP = {re.sub(r"[^a-z0-9]", "", k): v for k, v in ALIAS_REP.items()}
ALIAS_CORE = {re.sub(r"[^a-z0-9]", "", k): v for k, v in ALIAS_CORE.items()}


class ParseError(Exception):
    pass


def key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def txt(c):
    return "" if c is None else " ".join(str(c).split())


def cells(row):
    return [t for t in (txt(c) for c in row) if t != ""]


def num(s):
    s = s.replace(",", "").replace("%", "").strip()
    if s.upper() in ("NR", "N/R", "-", "–", ""):
        return None
    try:
        return float(s)
    except ValueError:
        raise ParseError(f"not a number: {s!r}")


def week_to_date(year, week):          # identical to prepare_data.py
    try:
        return pd.Timestamp.fromisocalendar(int(year), int(week), 1)
    except Exception:
        return pd.NaT


# ----------------------------------------------------------------------------
# Website
# ----------------------------------------------------------------------------
def get(url, retries=3, timeout=120):
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last}")


def clean_url(url):
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def parse_links(html, base=PAGE_URL):
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for a in soup.find_all("a", href=True):
        if ".pdf" not in a["href"].lower():
            continue
        m = TITLE_RE.search(a.get_text(" ", strip=True))
        if m:
            found.setdefault((int(m.group(2)), int(m.group(1))),
                             clean_url(urljoin(base, a["href"])))
    return found


# ----------------------------------------------------------------------------
# Name resolution against what is already in your files
# ----------------------------------------------------------------------------
def known_names(df):
    """{province: {key: most common spelling}} from an existing dataframe."""
    out = {}
    for (prov, dist), n in df.groupby(["Province", "District"]).size().items():
        out.setdefault(prov, {}).setdefault(key(dist), Counter())[dist] += n
    return {p: {k: c.most_common(1)[0][0] for k, c in d.items()} for p, d in out.items()}


def resolve(name, province, known, alias, warnings):
    name = " ".join(name.split())
    k = key(name)
    if k in known.get(province, {}):
        return known[province][k]
    if k in alias:
        return alias[k]
    warnings.append(f"new district name for {province}: '{name}' (kept as written)")
    return name


def norm_province(s):
    k = key(s)
    if k in ("kp", "khyberpakhtunkhwa", "kpk"):
        return "KP"
    if k.startswith("azadjammu") or k == "ajk":
        return "Azad Jammu & Kashmir"
    if k.startswith("gilgit") or k == "gb":
        return "Gilgit-Baltistan"
    if k.startswith("islamabad") or k == "ict":
        return "Islamabad Capital Territory"
    if k == "sindh":
        return "Sindh"
    if k == "balochistan":
        return "Balochistan"
    if k == "punjab":
        return "Punjab"
    return None


# ----------------------------------------------------------------------------
# PDF reading
# ----------------------------------------------------------------------------
CAP = re.compile(r"Table\s*(\d+)\s*:\s*([^\n]*(?:\n[^\n]*)?)")


def locate_tables(pdf):
    """-> t1, district, t6, overview.  t1 / district[prov] = {'tables': [...], 'texts': [...]}"""
    t1 = {"tables": [], "texts": []}
    district, t6, overview = {}, [], {}
    state, prov = None, None
    for page in pdf.pages:
        text = page.extract_text() or ""
        for m in re.finditer(r"^(Khyber Pakhtunkhwa|Azad Jammu Kashmir|Islamabad Capital Territory|"
                             r"Balochistan|Gilgit Baltistan|Sindh)\s+(\d+)\s+(\d+)\s+(\d+)\s*$",
                             text, re.M):
            overview[norm_province(m.group(1))] = (int(m.group(2)), int(m.group(3)))
        m = CAP.search(text)
        if m:
            n, cap = int(m.group(1)), m.group(2)
            if n == 1:
                state = "t1"
            elif re.search(r"District\s*wise", cap, re.I):
                state = "district"
                pm = re.search(r"Week\s*\d+\s*,?\s*([A-Za-z ]+)", cap)
                prov = norm_province(pm.group(1).strip()) if pm else None
            elif re.search(r"Compliance of IDSR reporting districts", cap, re.I):
                state = "t6"
            else:
                state = None
        if state is None:
            continue
        tabs = [t for t in page.extract_tables()
                if len(t) >= 3 and max(len(r) for r in t) >= 4 and sum(1 for r in t if cells(r)) >= 3]
        if not tabs:
            continue
        if state == "t1":
            t1["tables"] += tabs[:1]; t1["texts"].append(text)
        elif state == "district":
            d = district.setdefault(prov, {"tables": [], "texts": []})
            d["tables"] += tabs[:1]; d["texts"].append(text)
        elif state == "t6":
            t6 += tabs
    return t1, district, t6, overview


def is_data_row(row):
    c = cells(row)
    return len(c) >= 2 and all(re.fullmatch(r"[\d,]+|NR|-", x) for x in c[1:])


NUM_TOKEN = re.compile(r"^(\d{1,3}(,\d{3})+|\d+|NR|-)$")


def read_header(tables):
    for t in tables:
        i0 = next((i for i, r in enumerate(t) if is_data_row(r)), None)
        if i0:
            hdr = t[:i0]                               # header may wrap over 2 rows: join column by column
            width = max(len(r) for r in hdr)
            joined = [" ".join(x for x in (txt(r[i]) if i < len(r) else "" for r in hdr) if x)
                      for i in range(width)]
            return [h for h in joined if h][1:]        # drop the first label (Districts / Diseases)
    raise ParseError("table header not found")


def read_case_table(block):
    """block = {'tables': [...], 'texts': [...]}.
    Header comes from the table; rows come from the page text, because long names
    (e.g. 'Karachi / Central') wrap onto two lines and the table grid splits them badly.
    -> (header_names, {row_name: [values]}, total_values)"""
    header = read_header(block["tables"])
    n = len(header)
    rows, total, done = {}, None, False
    for text in block["texts"]:
        started, prefix = False, []
        for line in text.splitlines():
            tok = line.split()
            if len(tok) > n and all(NUM_TOKEN.match(x) for x in tok[-n:]):
                name = " ".join(prefix + tok[:-n]).strip()
                prefix, started = [], True
                vals = [num(x) for x in tok[-n:]]
                if key(name) == "total":
                    total, done = vals, True
                    break
                if name in rows:
                    raise ParseError(f"row '{name}' appears twice")
                rows[name] = vals
            elif started and len(tok) <= 4 and re.fullmatch(r"[A-Za-z][A-Za-z .&()/\-]*", line.strip()):
                prefix.append(line.strip())
            else:
                prefix = []
        if done:
            break
    if not rows:
        raise ParseError("no data rows found")
    return header, rows, total


def read_compliance(tables):
    """Rows look like [province?] district total reported rate%.  The rate cell is sometimes
    pushed onto its own row, so a row without a % is held until the next row supplies it."""
    out, prov, pending = [], None, None
    for t in tables:
        for r in t:
            c = cells(r)
            if not c:
                continue
            if len(c) == 1 and c[0].endswith("%"):
                if pending is not None:
                    out.append(pending + (num(c[0]),))
                    pending = None
                elif not out or out[-1][4] != num(c[0]):
                    raise ParseError(f"stray rate {c[0]}")
                continue                                 # (a rate repeated on its own row is ignored)
            rate = None
            if c[-1].endswith("%"):
                rate, c = num(c[-1]), c[:-1]
            if c and c[0] == "Territory":               # 2nd line of "Islamabad Capital Territory"
                c = c[1:]
            if len(c) < 3 or not (re.fullmatch(r"\d+", c[-1]) and re.fullmatch(r"\d+", c[-2])):
                continue                                 # header / junk row
            total, reported, names = int(c[-2]), int(c[-1]), c[:-2]
            if len(names) >= 2:
                p = norm_province(names[0])
                if p:
                    prov, names = p, names[1:]
            if len(names) != 1 or prov is None:
                raise ParseError(f"cannot read compliance row {c}")
            item = (prov, names[0], total, reported)
            if rate is None:
                pending = item
            else:
                out.append(item + (rate,))
    if pending is not None:
        raise ParseError(f"compliance row without a rate: {pending}")
    return out


def parse_bulletin(content, year, week, known_core, known_rep, strict=True):
    """Return (core_rows, rep_rows, warnings). Raises ParseError if anything does not add up."""
    warnings, problems = [], []
    pdf = pdfplumber.open(io.BytesIO(content))

    head = " ".join((pdf.pages[i].extract_text() or "") for i in range(min(4, len(pdf.pages))))
    m = re.search(r"Week\s*(\d{1,2})\s*,\s*(20\d{2})", head)
    if m and (int(m.group(2)), int(m.group(1))) != (year, week):
        raise ParseError(f"PDF says week {m.group(1)}/{m.group(2)} but link says {week}/{year}")
    if not m:
        warnings.append("could not confirm week/year inside the PDF")

    t1, district, t6, overview = locate_tables(pdf)

    # Table 1 (province totals) used only to cross-check the district tables
    prov1 = {}
    if t1["tables"]:
        pcols, rows, _ = read_case_table(t1)
        for disease, vals in rows.items():
            for pname, v in zip(pcols, vals):
                prov1[(key(disease), pname)] = v

    # ---- core rows
    core_rows = []
    by_prov = district
    if not by_prov:
        raise ParseError("no district-wise tables found")
    for prov, tabs in by_prov.items():
        if prov not in ("Sindh", "Balochistan", "KP"):
            warnings.append(f"skipped district table for {prov}")
            continue
        dhead, rows, total = read_case_table(tabs)
        dkeys = [key(h) for h in dhead]
        unknown = [d for d in dkeys if d not in DISEASE_FULL]
        if unknown:
            raise ParseError(f"{prov}: unknown disease column(s) {unknown}")
        diseases = [DISEASE_FULL[d] for d in dkeys]
        # check 1: districts add up to the Total row
        if total is None:
            raise ParseError(f"{prov}: no Total row")
        for j, d in enumerate(diseases):
            s = sum((r[j] or 0) for r in rows.values())
            if s != (total[j] or 0):
                problems.append(f"{prov} {d}: districts add to {s:g} but Total row says {(total[j] or 0):g}")
        # check 2: Total row equals Table 1
        label = {"KP": "KP", "Sindh": "Sindh", "Balochistan": "Balochistan"}[prov]
        for j, dk in enumerate(dkeys):
            v1 = prov1.get((dk, label))
            if v1 is not None and v1 != (total[j] or 0):
                problems.append(f"{prov} {diseases[j]}: district total {(total[j] or 0):g} vs Table 1 {v1:g}")
        seen = set()
        for dname, vals in rows.items():
            dist = resolve(dname, prov, known_core, ALIAS_CORE, warnings)
            if dist in seen:
                raise ParseError(f"{prov}: district '{dist}' appears twice")
            seen.add(dist)
            for d, v in zip(diseases, vals):
                core_rows.append({"Year": year, "Week": week, "Disease": d, "Clean Disease": d,
                                  "District": dist, "Value": float(v or 0),   # NR -> 0, as in prepare_data.py
                                  "Province": prov, "Category": DISEASE_CATEGORY.get(d, "Other / neglected tropical")})

    # ---- reporting rows (optional table)
    rep_rows = []
    if t6:
        comp = read_compliance(t6)
        sums = {}
        seen = set()
        for prov, dname, total, reported, rate in comp:
            if total > 0 and abs(round(reported / total * 100) - rate) > 1:
                problems.append(f"compliance {dname}: {reported}/{total} is not {rate:g}%")
            dist = resolve(dname, prov, known_rep, ALIAS_REP, warnings)
            if (prov, dist) in seen:
                raise ParseError(f"reporting: '{dist}' appears twice")
            seen.add((prov, dist))
            s = sums.setdefault(prov, [0, 0]); s[0] += total; s[1] += reported
            rep_rows.append({"Year": year, "Week": week, "Province": prov, "District": dist,
                             "Reporting_Sites_ARS": reported, "Reporting_Sites_Total": float(total),
                             "Sites_Reported_Current_Week": reported, "Agreed_Reporting_Sites": float(total),
                             "Compliance_Rate_Pct": float(rate), "Reporting_Rate_Pct": float("nan")})
        for p, (exp, rec) in overview.items():
            if p in sums and tuple(sums[p]) != (exp, rec):
                warnings.append(f"{p}: overview says {exp}/{rec} sites, Table 6 adds to {sums[p][0]}/{sums[p][1]}")
    else:
        warnings.append("no compliance table (Table 6) in this bulletin")

    if problems and not strict:
        warnings.extend("NOT MATCHING (accepted): " + p for p in problems)
        problems = []
    if problems:
        raise ParseError("; ".join(problems[:8]) + (f" (+{len(problems)-8} more)" if len(problems) > 8 else ""))
    return core_rows, rep_rows, warnings


# ----------------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------------
def save_parquet(df, path):
    path = Path(path)
    if path.exists():
        shutil.copy2(path, str(path) + ".bak")          # one safety copy, overwritten each run
    tmp = str(path) + ".tmp"
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def build_core_frame(rows, like):
    df = pd.DataFrame(rows)
    df["Date"] = [week_to_date(y, w) for y, w in zip(df["Year"], df["Week"])]
    df["Month"] = df["Date"].dt.month
    df["MonthName"] = df["Date"].dt.strftime("%b")
    df = df[list(like.columns)]
    return df.astype({c: like[c].dtype for c in like.columns if c != "Date"}, errors="ignore")



# ----------------------------------------------------------------------------
# Quarantine list of weeks that could not be read
# ----------------------------------------------------------------------------
def load_skipped(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_skipped(path, data):
    p = Path(path)
    if data:
        p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    elif p.exists():
        p.unlink()


def is_quarantined(info):
    try:
        age = (date.today() - date.fromisoformat(info["last_try"])).days
    except (KeyError, ValueError, TypeError):
        return False
    return age < RETRY_AFTER_DAYS


def report_failures(failed):
    """Visible on the GitHub run page without turning the whole run red."""
    lines = [f"{y}-W{w:02d}: {why}" for y, w, why in failed]
    for l in lines:
        print(f"::warning title=IDSR week skipped::{l[:400]}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("### Weeks skipped by update_data.py\n\n")
            f.write("\n".join(f"- `{l}`" for l in lines) + "\n")


RECENT_WEEKS = 8


def _recent_counts(df, province_col="Province", dist_col="District"):
    """{province: median number of districts per week over the last RECENT_WEEKS weeks in the file}"""
    wk = df[["Year", "Week"]].drop_duplicates().sort_values(["Year", "Week"]).tail(RECENT_WEEKS)
    sub = df.merge(wk, on=["Year", "Week"])
    per = sub.groupby([province_col, "Year", "Week"])[dist_col].nunique().reset_index()
    return per.groupby(province_col)[dist_col].median().to_dict()


def hard_checks(core_rows, rep_rows, core, rep):
    """Problems that can never be accepted, not even with --accept-mismatch: they mean the PDF was
    read wrongly (garbled names, missing or invented districts), so saving would corrupt the data."""
    problems = []
    for label, rows in (("cases", core_rows), ("reporting", rep_rows)):
        for n in sorted({r["District"] for r in rows}):
            if "(cid:" in n or n[:1].islower() or len(n) < 3:
                problems.append(f"{label}: garbled district name {n!r}")
    for label, rows, ref_df in (("cases", core_rows, core), ("reporting", rep_rows, rep)):
        if not rows:
            continue
        ref = _recent_counts(ref_df)
        got = pd.DataFrame(rows).groupby("Province")["District"].nunique().to_dict()
        for prov, n in got.items():
            r = ref.get(prov)
            if r and not (0.9 * r <= n <= 1.15 * r):
                problems.append(f"{label}: {prov} has {n} districts, recent weeks have about {r:g}")
        for prov, r in ref.items():
            if label == "cases" and prov not in got:
                problems.append(f"cases: {prov} is missing (recent weeks have about {r:g} districts)")
    if problems:
        raise ParseError("; ".join(problems[:6]) + (f" (+{len(problems)-6} more)" if len(problems) > 6 else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="process just this week, e.g. 2025-52")
    ap.add_argument("--backfill-reporting", action="store_true")
    ap.add_argument("--accept-mismatch", action="store_true")
    ap.add_argument("--retry-skipped", action="store_true",
                    help="retry weeks in skipped_weeks.json even if tried recently")
    ap.add_argument("--strict-exit", action="store_true",
                    help="exit with code 1 if any week was skipped")
    args = ap.parse_args()

    core_p = Path(args.data_dir) / "core.parquet"
    rep_p = Path(args.data_dir) / "reporting.parquet"
    skip_p = Path(args.data_dir) / SKIP_FILE
    skipped = load_skipped(skip_p)
    core = pd.read_parquet(core_p)
    rep = pd.read_parquet(rep_p)
    core_weeks = set(zip(core.Year.astype(int), core.Week.astype(int)))
    rep_weeks = set(zip(rep.Year.astype(int), rep.Week.astype(int)))

    links = parse_links(get(PAGE_URL).text)
    if not links:
        sys.exit("ERROR: no bulletin links found - the website layout may have changed.")

    todo = [k for k in sorted(links)
            if k not in core_weeks or (args.backfill_reporting and k not in rep_weeks)]
    if args.only:
        y, w = map(int, args.only.split("-"))
        todo = [(y, w)] if (y, w) in links else []
    elif not args.retry_skipped:
        held = [k for k in todo if is_quarantined(skipped.get(f"{k[0]}-{k[1]}", {}))]
        if held:
            print(f"{len(held)} earlier-failed week(s) not retried yet (retry after {RETRY_AFTER_DAYS} days): "
                  + ", ".join(f"{y}-W{w:02d}" for y, w in held))
        todo = [k for k in todo if k not in held]
    if not todo:
        print("No data found")
        return

    print(f"{len(todo)} week(s) to add: " + ", ".join(f"{y}-W{w:02d}" for y, w in todo))
    if args.dry_run:
        return

    known_core, known_rep = known_names(core), known_names(rep)
    new_core, new_rep, failed = [], [], []
    for y, w in todo:
        try:
            content = get(links[(y, w)]).content
            if not content.startswith(b"%PDF"):
                raise ParseError("download is not a PDF")
            c_rows, r_rows, warns = parse_bulletin(content, y, w, known_core, known_rep,
                                                   strict=not args.accept_mismatch)
            hard_checks(c_rows, r_rows, core, rep)
        except ParseError as e:
            failed.append((y, w, str(e)))
            print(f"  {y}-W{w:02d}: SKIPPED - {e}")
            continue
        except Exception as e:                           # network / unexpected
            failed.append((y, w, repr(e)))
            print(f"  {y}-W{w:02d}: FAILED - {e!r}")
            continue
        skipped.pop(f"{y}-{w}", None)                    # read fine this time: release from quarantine
        add_core = (y, w) not in core_weeks
        add_rep = (y, w) not in rep_weeks and bool(r_rows)
        if add_core:
            new_core += c_rows
        if add_rep:
            new_rep += r_rows
        print(f"  {y}-W{w:02d}: {len(c_rows) if add_core else 0} case rows, "
              f"{len(r_rows) if add_rep else 0} compliance rows")
        for x in warns:
            print(f"      warning: {x}")
        time.sleep(1)

    today = date.today().isoformat()
    for y, w, why in failed:
        old = skipped.get(f"{y}-{w}", {})
        skipped[f"{y}-{w}"] = {"reason": why[:500], "last_try": today, "tries": old.get("tries", 0) + 1}
    save_skipped(skip_p, skipped)

    if new_core:
        add = build_core_frame(new_core, core)
        out = pd.concat([core, add], ignore_index=True)
        assert not add.duplicated(["Year", "Week", "Province", "District", "Clean Disease"]).any(), "duplicate rows"
        assert not (set(zip(add.Year, add.Week)) & core_weeks), "week already in file"
        save_parquet(out, core_p)
    if new_rep:
        add = pd.DataFrame(new_rep)[list(rep.columns)].astype(
            {c: rep[c].dtype for c in rep.columns}, errors="ignore")
        assert not add.duplicated(["Year", "Week", "District"]).any(), "duplicate reporting rows"
        assert not (set(zip(add.Year, add.Week)) & rep_weeks), "week already in reporting file"
        out = pd.concat([rep, add], ignore_index=True)
        save_parquet(out, rep_p)

    print(f"Done: {len({(r['Year'], r['Week']) for r in new_core})} week(s) added to core.parquet, "
          f"{len({(r['Year'], r['Week']) for r in new_rep})} to reporting.parquet, {len(failed)} skipped.")
    if failed:
        report_failures(failed)
        if args.strict_exit:
            sys.exit(1)


if __name__ == "__main__":
    main()
