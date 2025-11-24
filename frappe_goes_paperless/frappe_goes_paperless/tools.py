# Copyright (c) 2024, itsdave GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.password import get_decrypted_password
import requests
import re
from datetime import date

@frappe.whitelist()
def installed_apps():
    return ['ai_workflows']

def get_paperless_settings():
    settings = frappe.get_doc("Paperless-ngx Settings", "Paperless-ngx Settings")
    api_token = get_decrypted_password(
        doctype="Paperless-ngx Settings",
        name="Paperless-ngx Settings",
        fieldname="api_token",
        raise_exception=False,
    )
    return settings.paperless_ngx_server, api_token


def get_paperless_ids():
    server_url, api_token = get_paperless_settings()
    response = requests.get(
        f"{server_url.rstrip('/')}/api/documents/",
        headers={
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json",
        },
    )
    if response.status_code == 200:
        if len(response.json()) > 0:
            return response.json()["all"]
    return None


def get_paperless_fulltext(document_id):
    server_url, api_token = get_paperless_settings()
    response = requests.get(
        f"{server_url.rstrip('/')}/api/documents/{document_id}/",
        headers={
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json",
        },
    )
    if response.status_code == 200:
        if len(response.json()) > 0:
            return response.json()["content"]
    return None


# Get data from paperless-ngx
def paperless_api(place, id):
    server_url, api_token = get_paperless_settings()
    response = requests.get(
        f"{server_url.rstrip('/')}/api/{place}/{id}/",
        headers={
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json",
        },
    )
    if response.status_code == 200:
        if len(response.json()) > 0:
            return response.json()
    return None


# Get document thumbprint image
def get_paperless_docthumb(id, docname):
    server_url, api_token = get_paperless_settings()
    response = requests.get(
        f"{server_url.rstrip('/')}/api/documents/{id}/thumb/",
        headers={"Authorization": f"Token {api_token}"},
    )
    if response.status_code == 200:
        if response.content:
            file_doc = frappe.new_doc("File")
            file_doc.file_name = f"docthumb-{id}.webp"
            file_doc.attached_to_doctype = "Paperless Document"
            file_doc.attached_to_name = docname
            file_doc.content = response.content
            file_doc.decode = False
            file_doc.is_private = False
            file_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return file_doc.file_url
    return None


@frappe.whitelist()
def sync_documents(paperless_document=None):
    # Get all ids from paperless
    if paperless_document:
        ids = [paperless_document]
    else:
        ids = get_paperless_ids()
    if not ids:
        return False
    # get all ids from frappe
    docs = frappe.get_all("Paperless Document", fields=["paperless_document_id"])
    # Get a array with missing ids (compare the two lists of ids)
    mis = list(
        set(ids)
        - set(
            [
                int(id["paperless_document_id"])
                for id in docs
                if id.get("paperless_document_id") is not None
            ]
        )
    )
    for id in mis:
        try:
            get_document = paperless_api("documents", id)
            if not get_document:
                continue
            # Get frappe doctype by Paperless doctype
            response = paperless_api("document_types", get_document["document_type"])
            if response is not None:
                paperless_doctype = response["name"]
            else:
                paperless_doctype = None
            frappe_doctype = frappe.get_all(
                "Paperless Document Type Mapping",
                fields=["frappe_doctype"],
                filters={"paperless_document_type": paperless_doctype},
            )
            frappe_doctype = (
                frappe_doctype[0]["frappe_doctype"] if len(frappe_doctype) > 0 else None
            )

            # add document
            new_doc = frappe.new_doc("Paperless Document")
            new_doc.paperless_document_id = id
            correspondent = paperless_api(
                "correspondents", get_document["correspondent"]
            )
            new_doc.paperless_correspondent = (
                correspondent["name"] if correspondent else None
            )
            new_doc.paperless_documenttype = paperless_doctype
            new_doc.status = "new"
            new_doc.frappe_doctype = frappe_doctype
            new_doc.document_fulltext = get_document["content"]
            # -> Rechnungsdatum aus dem Volltext ziehen
            invoice_date = extract_invoice_date_from_text(new_doc.document_fulltext)
            if invoice_date:
                new_doc.invoice_date = invoice_date
            new_doc.save()
            thumbimage = get_paperless_docthumb(id, new_doc.name)
            if thumbimage:
                new_doc.thumbprint = thumbimage
            new_doc.save()
            frappe.db.commit()
            print(f"Document added -> {get_document['title']}")
        except Exception as e:
            # Handle HTTP errors
            msg = f"Failed to fetch documents from Paperless-ngx: {e}"
            print(msg)
            frappe.log_error(msg)


@frappe.whitelist()
def job_status(jobid):
    getStatus = None
    getJob = [
        (j.job_id, j.status)
        for j in frappe.get_all("RQ Job", filters={"job_id": jobid})
        if j.job_id == jobid
    ]
    if len(getJob) > 0:
        for job_id, status in getJob:
            if job_id == jobid:
                getStatus = status
                break
    return getStatus

# # Monatsnamen-Datum parsen
# def parse_date_with_month_name(raw: str):
#     """Versucht Datumsangaben wie '30 Oktober 2025' oder '30 October 2025' zu parsen.
#     Gibt ein date-Objekt oder None zurück.
#     """
#     if not raw:
#         return None

#     # alles etwas normalisieren
#     txt = " ".join(raw.replace("\n", " ").split())
#     parts = txt.split(" ")
#     if len(parts) < 3:
#         return None

#     # einfache Annahme: <Tag> <Monatsname> <Jahr>
#     # z.B. 30 Oktober 2025 oder 30. Oktober 2025
#     try:
#         day_str = parts[0].rstrip(".")
#         day = int(day_str)
#     except Exception:
#         return None

#     # Monatsname kann an zweiter Stelle sein
#     month_word = parts[1].strip().rstrip(".").lower()

#     month_map = {
#         # Deutsch
#         "januar": 1, "jan": 1,
#         "februar": 2, "feb": 2,
#         "märz": 3, "maerz": 3, "mrz": 3,
#         "april": 4, "apr": 4,
#         "mai": 5,
#         "juni": 6, "jun": 6,
#         "juli": 7, "jul": 7,
#         "august": 8, "aug": 8,
#         "september": 9, "sept": 9, "sep": 9,
#         "oktober": 10, "okt": 10,
#         "november": 11, "nov": 11,
#         "dezember": 12, "dez": 12,
#         # Englisch (für Sicherheit)
#         "january": 1,
#         "february": 2,
#         "march": 3,
#         "april": 4,
#         "may": 5,
#         "june": 6,
#         "july": 7,
#         "august": 8,
#         "september": 9,
#         "october": 10,
#         "november": 11,
#         "december": 12,
#     }

#     month = month_map.get(month_word)
#     if not month:
#         return None

#     # Jahr sollte das letzte Element sein
#     try:
#         year = int(parts[-1].rstrip("."))
#     except Exception:
#         return None

#     if year < 1900 or year > 2100:
#         return None

#     try:
#         return date(year, month, day)
#     except Exception:
#         return None


# def extract_invoice_date_from_text(text: str):
#     """Einfache, robuste Datumserkennung für Rechnungen/Quittungen.

#     - bevorzugt 'Rechnungsdatum 02.11.2020'
#     - unterstützt dd.mm.yyyy, dd-mm-yyyy, dd/mm/yyyy, ISO und Monatsnamen
#     """

#     if not text:
#         return None

#     # Normalisieren
#     normalized = " ".join(text.replace("\n", " ").split())
#     lower = normalized.lower()

#     # Relevante Keywords
#     keywords = [
#         "rechnungsdatum",
#         "quittungsdatum",
#         "invoice date",
#         "belegdatum",
#         "rechnung vom",
#         "datum",
#     ]

#     # Muster
#     numeric_pattern = re.compile(r"(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})")   # 02.11.2020, 02-11-2020
#     iso_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")                     # 2020-11-02
#     word_pattern = re.compile(r"(\d{1,2}\s+[A-Za-zÄÖÜäöüß\.]+\s+\d{4})") # 30 Oktober 2025

#     def _is_plausible(d):
#         return d and str(d) >= "2010-01-01"

#     def _parse_loose(raw: str):
#         """Versuch 1: frappe.utils.parse_date, Versuch 2: dd.mm.yyyy selber parsen."""
#         if not raw:
#             return None

#         # Erst Frappe probieren
#         try:
#             d = frappe.utils.parse_date(raw)
#             if d:
#                 return d
#         except Exception:
#             pass

#         # Dann dd.mm.yyyy / dd-mm-yyyy / dd/mm/yyyy selbst parsen
#         sep = "." if "." in raw else "-" if "-" in raw else "/" if "/" in raw else None
#         if not sep:
#             return None

#         try:
#             day, month, year = raw.split(sep)
#             day = int(day)
#             month = int(month)
#             year = int(year)
#             if year < 2000 or year > 2100:
#                 return None
#             return date(year, month, day)
#         except Exception:
#             return None

#     # 1) Keyword + Datum dahinter
#     for kw in keywords:
#         idx = lower.find(kw)
#         if idx == -1:
#             continue

#         snippet = normalized[idx:idx + 150]

#         # 1a) numerisch
#         for raw in numeric_pattern.findall(snippet):
#             parsed = _parse_loose(raw)
#             if _is_plausible(parsed):
#                 return parsed

#         # 1b) ISO
#         for raw in iso_pattern.findall(snippet):
#             parsed = _parse_loose(raw)
#             if _is_plausible(parsed):
#                 return parsed

#         # 1c) Monatsnamen
#         for raw in word_pattern.findall(snippet):
#             parsed = parse_date_with_month_name(raw)
#             if _is_plausible(parsed):
#                 return parsed

#     # 2) Fallback: irgendwo im Text numerische Datumsangaben
#     for raw in numeric_pattern.findall(normalized):
#         parsed = _parse_loose(raw)
#         if _is_plausible(parsed):
#             return parsed

#     # 3) Fallback: ISO
#     for raw in iso_pattern.findall(normalized):
#         parsed = _parse_loose(raw)
#         if _is_plausible(parsed):
#             return parsed

#     # 4) Fallback: Monatsnamen
#     for raw in word_pattern.findall(normalized):
#         parsed = parse_date_with_month_name(raw)
#         if _is_plausible(parsed):
#             return parsed

#     return None

# GER_MONTHS = {
#     "januar": "01", "jan": "01",
#     "februar": "02", "feb": "02",
#     "märz": "03", "maerz": "03", "mrz": "03",
#     "april": "04", "apr": "04",
#     "mai": "05",
#     "juni": "06", "jun": "06",
#     "juli": "07", "jul": "07",
#     "august": "08", "aug": "08",
#     "september": "09", "sept": "09", "sep": "09",
#     "oktober": "10", "okt": "10",
#     "november": "11", "nov": "11",
#     "dezember": "12", "dez": "12",
# }

# EN_MONTHS = {
#     "january": "01", "jan": "01",
#     "february": "02", "feb": "02",
#     "march": "03", "mar": "03",
#     "april": "04", "apr": "04",
#     "may": "05",
#     "june": "06", "jun": "06",
#     "july": "07", "jul": "07",
#     "august": "08", "aug": "08",
#     "september": "09", "sep": "09", "sept": "09",
#     "october": "10", "oct": "10",
#     "november": "11", "nov": "11",
#     "december": "12", "dec": "12",
# }


# def _parse_numeric_date(raw: str):
#     """Parst 20.10.2025 UND 20.10.25 robust."""
#     parts = re.split(r"[.\-/]", raw)
#     if len(parts) != 3:
#         return None

#     d, m, y = [p.strip() for p in parts]

#     # 2-stellige Jahreszahl nach 2000 heben (Heuristik)
#     if len(y) == 2:
#         try:
#             y_int = int(y)
#         except ValueError:
#             return None
#         if y_int <= 50:
#             y = f"20{y}"
#         else:
#             y = f"19{y}"

#     try:
#         d = d.zfill(2)
#         m = m.zfill(2)
#         iso = f"{y}-{m}-{d}"
#         return frappe.utils.getdate(iso)
#     except Exception:
#         # Fallback: parse_date probieren
#         try:
#             return frappe.utils.parse_date(raw)
#         except Exception:
#             return None


# def parse_date_with_month_name(raw: str):
#     """Unterstützt:
#     - '30 Oktober 2025'
#     - 'Oct 25, 2025'
#     - 'October 14, 2025'
#     """
#     s = raw.strip()

#     # Variante 1: Tag Monat Jahr  -> 30 Oktober 2025
#     m1 = re.match(r"(\d{1,2})\s+([A-Za-zÄÖÜäöüß\.]+)\s+(\d{4})", s)
#     if m1:
#         d, mon, y = m1.groups()
#         mon_key = mon.lower().strip(".")
#         month = GER_MONTHS.get(mon_key) or EN_MONTHS.get(mon_key)
#         if not month:
#             return None
#         d = d.zfill(2)
#         iso = f"{y}-{month}-{d}"
#         try:
#             return frappe.utils.getdate(iso)
#         except Exception:
#             return None

#     # Variante 2: Monat Tag, Jahr  -> October 14, 2025 / Oct 25 2025
#     m2 = re.match(r"([A-Za-zÄÖÜäöüß\.]+)\s+(\d{1,2}),?\s+(\d{4})", s)
#     if m2:
#         mon, d, y = m2.groups()
#         mon_key = mon.lower().strip(".")
#         month = GER_MONTHS.get(mon_key) or EN_MONTHS.get(mon_key)
#         if not month:
#             return None
#         d = d.zfill(2)
#         iso = f"{y}-{month}-{d}"
#         try:
#             return frappe.utils.getdate(iso)
#         except Exception:
#             return None

#     return None


# def extract_invoice_date_from_text(text: str):
#     """Einfache, robuste Datumserkennung für Rechnungen/Quittungen.

#     Strategie:
#     0. Spezieller Fallback für ISO-Datum mit Uhrzeit/Zeitzone, z.B.
#        '2025-11-05 11:16AM PST' → 2025-11-05
#     1. Suche nach 'Rechnungsdatum', 'Quittungsdatum', 'Invoice Date',
#        'Datum', etc. und nimm das erste Datum danach.
#     2. Wenn dort nichts gefunden wird: nimm das erste plausible Datum im gesamten Text.
#     """

#     if not text:
#         return None

#     # Normalisieren
#     normalized = " ".join(text.replace("\n", " ").split())
#     lower = normalized.lower()

#     # Relevante Keywords
#     keywords = [
#         "rechnungsdatum",
#         "quittungsdatum",
#         "invoice date",
#         "belegdatum",
#         "rechnung vom",
#         "datum",
#         "due",              # z.B. "due October 14, 2025"
#     ]

#     # Muster
#     numeric_pattern = re.compile(r"(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})")   # 02.11.2020 / 20.10.25
#     iso_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")                       # 2025-11-05
#     word_pattern = re.compile(r"(\d{1,2}\s+[A-Za-zÄÖÜäöüß\.]+\s+\d{4})")   # 30 Oktober 2025

#     def _is_plausible(d):
#         # Rechnungsdatum – alles nach 2010 sollte passen
#         if not d:
#             return False
#         try:
#             d = frappe.utils.getdate(d)
#         except Exception:
#             return False
#         return d >= frappe.utils.getdate("2010-01-01")

#     def _parse_numeric(raw: str):
#         # z.B. '20.10.25.' → '20.10.25'
#         raw_clean = raw.rstrip(".")
#         try:
#             return frappe.utils.parse_date(raw_clean)
#         except Exception:
#             return None

#     # 0) Spezieller Fallback: ISO-Datum irgendwo im Text, z.B.
#     #    "2025-11-05 11:16AM PST" → wir fischen nur "2025-11-05" raus
#     m = re.search(r"(\d{4}-\d{2}-\d{2})", normalized)
#     if m:
#         parsed = _parse_numeric(m.group(1))
#         if _is_plausible(parsed):
#             return parsed

#     # 1) Keyword + Datum dahinter
#     for kw in keywords:
#         idx = lower.find(kw)
#         if idx == -1:
#             continue

#         # kurzer Ausschnitt um das Keyword
#         snippet = normalized[idx:idx + 200]

#         # 1a) numerisch (02.11.2020, 20-10-25, ...)
#         for raw in numeric_pattern.findall(snippet):
#             parsed = _parse_numeric(raw)
#             if _is_plausible(parsed):
#                 return parsed

#         # 1b) ISO (2025-11-05)
#         for raw in iso_pattern.findall(snippet):
#             parsed = _parse_numeric(raw)
#             if _is_plausible(parsed):
#                 return parsed

#         # 1c) mit ausgeschriebenem Monat (30 Oktober 2025, Oct 25, 2025)
#         for raw in word_pattern.findall(snippet):
#             parsed = parse_date_with_month_name(raw)
#             if _is_plausible(parsed):
#                 return parsed

#     # 2) Fallback: überall im Text numerische Datumsangaben
#     for raw in numeric_pattern.findall(normalized):
#         parsed = _parse_numeric(raw)
#         if _is_plausible(parsed):
#             return parsed

#     # 3) Fallback: überall ISO (nur Datumsteil)
#     for raw in iso_pattern.findall(normalized):
#         parsed = _parse_numeric(raw)
#         if _is_plausible(parsed):
#             return parsed

#     # 4) Fallback: ausgeschriebene Monate
#     for raw in word_pattern.findall(normalized):
#         parsed = parse_date_with_month_name(raw)
#         if _is_plausible(parsed):
#             return parsed

#     return None

MONTH_NAME_MAP = {
    # Deutsch
    "januar": "01", "jan": "01", "jan.": "01",
    "februar": "02", "feb": "02", "feb.": "02",
    "märz": "03", "maerz": "03", "mrz": "03", "mrz.": "03",
    "april": "04", "apr": "04", "apr.": "04",
    "mai": "05",
    "juni": "06", "jun": "06", "jun.": "06",
    "juli": "07", "jul": "07", "jul.": "07",
    "august": "08", "aug": "08", "aug.": "08",
    "september": "09", "sep": "09", "sep.": "09", "sept": "09", "sept.": "09",
    "oktober": "10", "okt": "10", "okt.": "10",
    "november": "11", "nov": "11", "nov.": "11",
    "dezember": "12", "dez": "12", "dez.": "12",

    # Englisch
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10", "oct": "10", "oct.": "10",
    "november": "11",
    "december": "12", "dec": "12", "dec.": "12",
}


def parse_date_with_month_name(text: str):
    """Parst Datumsangaben mit ausgeschriebenem Monat (de/en).

    Beispiele:
    - '30 Oktober 2025'
    - 'October 14, 2025'
    - 'Invoice Date Oct 25, 2025'
    """

    if not text:
        return None

    s = text.lower()

    # Satzzeichen / Trenner in Spaces umwandeln
    for ch in [",", ";", "(", ")", "|", "-", "/", "."]:
        s = s.replace(ch, " ")

    # aus mehreren Whitespaces eins machen
    s = " ".join(s.split())

    # Regex-Baustein für alle bekannten Monatsnamen
    month_alternatives = "|".join(re.escape(m) for m in MONTH_NAME_MAP.keys())

    # Variante 1: 14 oktober 2025
    pattern1 = re.compile(
        rf"(\d{{1,2}})\s+({month_alternatives})\s+(\d{{2,4}})",
        re.IGNORECASE,
    )
    # Variante 2: october 14 2025  / october 14, 2025
    pattern2 = re.compile(
        rf"({month_alternatives})\s+(\d{{1,2}})\s+(\d{{2,4}})",
        re.IGNORECASE,
    )

    m = pattern1.search(s)
    if not m:
        m = pattern2.search(s)

    if not m:
        return None

    if m.re is pattern1:
        day, month_name, year = m.groups()
    else:
        month_name, day, year = m.groups()

    month_name = month_name.lower()
    month = MONTH_NAME_MAP.get(month_name)
    if not month:
        return None

    day = int(day)
    if not (1 <= day <= 31):
        return None

    # zwei-stellige Jahre -> 20xx
    if len(year) == 2:
        year = "20" + year
    year = int(year)

    try:
        return frappe.utils.getdate(f"{year:04d}-{month}-{day:02d}")
    except Exception:
        return None

def extract_invoice_date_from_text(text: str):
    """Einfache, robuste Datumserkennung für Rechnungen/Quittungen.

    Strategie:
    1. Suche nach 'Rechnungsdatum', 'Quittungsdatum', 'Invoice Date',
       'due', 'Belegdatum', 'Datum', usw. und nimm das erste Datum danach.
    2. Falls dort nichts gefunden wird: nimm das erste plausible Datum im Text.
    """

    if not text:
        return None

    # Normalisieren
    normalized = " ".join(text.replace("\n", " ").split())
    normalized = re.sub(r"(?<=\d),(?=\d)", ".", normalized)
    lower = normalized.lower()

    # Keywords, nach denen wir bevorzugt in der Nähe suchen
    keywords = [
        "rechnungsdatum",
        "quittungsdatum",
        "invoice date",
        "belegdatum",
        "rechnung vom",
        "due",
        "datum",
    ]

    # Muster
    numeric_pattern = re.compile(r"(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}\.?)")  # 20.10.25.
    iso_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")                        # 2025-11-05

    def _parse_numeric(raw: str):
        # Punkt am Ende abschneiden, z. B. 20.10.25.
        raw = raw.strip().rstrip(".")
        parts = re.split(r"[.\-/]", raw)
        if len(parts) != 3:
            return None
        d, m, y = parts
        d = int(d)
        m = int(m)
        if len(y) == 2:
            y = 2000 + int(y)
        else:
            y = int(y)
        try:
            return frappe.utils.getdate(f"{y:04d}-{m:02d}-{d:02d}")
        except Exception:
            return None

    def _is_plausible(d):
        return d and str(d) >= "2010-01-01"

    # 1) Erst in der Nähe der Keywords suchen
    for kw in keywords:
        idx = lower.find(kw)
        if idx == -1:
            continue

        snippet = normalized[idx: idx + 200]

        # 1a) numerische Formate (20.10.25., 20-10-2025)
        for raw in numeric_pattern.findall(snippet):
            parsed = _parse_numeric(raw)
            if _is_plausible(parsed):
                return parsed

        # 1b) ISO in der Nähe (2025-11-05)
        m = iso_pattern.search(snippet)
        if m:
            try:
                parsed = frappe.utils.getdate(m.group(1))
            except Exception:
                parsed = None
            if _is_plausible(parsed):
                return parsed


        # 1c) ausgeschriebener Monat in der Nähe (October 14, 2025 / 30 Oktober 2025)
        parsed = parse_date_with_month_name(snippet)
        if _is_plausible(parsed):
            return parsed

    # 2) Fallback: irgendwo im Text numerisch
    for raw in numeric_pattern.findall(normalized):
        parsed = _parse_numeric(raw)
        if _is_plausible(parsed):
            return parsed

    # 3) Fallback: ISO-Date im ganzen Text (z. B. '2025-11-05 11:16AM PST')
    m = iso_pattern.search(normalized)
    if m:
        try:
            parsed = frappe.utils.getdate(m.group(1))
        except Exception:
            parsed = None
        if _is_plausible(parsed):
            return parsed


    # 4) Fallback: ausgeschriebene Monate irgendwo im Text
    parsed = parse_date_with_month_name(normalized)
    if _is_plausible(parsed):
        return parsed

    return None



@frappe.whitelist()
def backfill_paperless_invoice_date(limit=10000, docname=None):
    """Setzt invoice_date für Paperless Document anhand von document_fulltext.

    - limit: Anzahl der Dokumente in einem Lauf (wird nur benutzt, wenn docname nicht gesetzt ist)
    - docname: wenn gesetzt, wird NUR dieses eine Paperless Document verarbeitet (Debug-Helfer)
    """

    docs = []

    if docname:
        # Nur ein Dokument gezielt bearbeiten
        row = frappe.db.get_value(
            "Paperless Document",
            docname,
            ["name", "document_fulltext", "invoice_date"],
            as_dict=True,
        )
        if not row:
            return {"total": 0, "updated": 0, "skipped": 0, "info": f"{docname} nicht gefunden"}
        docs = [row]
    else:
        # Alle ohne gesetztes invoice_date
        docs = frappe.get_all(
            "Paperless Document",
            filters={"invoice_date": ["is", "not set"]},
            fields=["name", "document_fulltext"],
            limit_page_length=limit,
        )

    updated = 0
    skipped = 0

    for row in docs:
        text = row.get("document_fulltext") or ""
        parsed = extract_invoice_date_from_text(text)

        # Debug-Ausgabe in die Konsole / Log
        print(f"[backfill] Doc {row['name']}: parsed={parsed}")

        if not parsed:
            skipped += 1
            continue

        doc = frappe.get_doc("Paperless Document", row["name"])
        doc.invoice_date = parsed
        doc.save(ignore_permissions=True)
        updated += 1

    frappe.db.commit()

    return {
        "total": len(docs),
        "updated": updated,
        "skipped": skipped,
    }


@frappe.whitelist()
def backfill_paperless_invoice_date_batch(batch_size=1000, max_batches=0):
    """Führt backfill_paperless_invoice_date in Batches aus, bis nichts mehr übrig ist
    oder max_batches erreicht ist.

    - batch_size: Anzahl Dokumente pro Batch
    - max_batches: 0 = unbegrenzt, sonst Abbruch nach so vielen Batches
    """

    batch_size = int(batch_size)
    max_batches = int(max_batches or 0)

    total_seen = 0
    total_updated = 0
    total_skipped = 0
    batch_no = 0

    while True:
        batch_no += 1
        res = backfill_paperless_invoice_date(limit=batch_size)

        batch_total = res.get("total") or 0
        batch_updated = res.get("updated") or 0
        batch_skipped = res.get("skipped") or 0

        total_seen += batch_total
        total_updated += batch_updated
        total_skipped += batch_skipped

        # etwas Feedback in der Console
        print(f"Batch {batch_no}: total={batch_total}, updated={batch_updated}, skipped={batch_skipped}")

        # wenn weniger als batch_size Dokumente im Batch waren, ist nichts mehr übrig
        if batch_total < batch_size:
            break

        # Sicherheitsbremse
        if max_batches and batch_no >= max_batches:
            break

    return {
        "batches": batch_no,
        "total_seen": total_seen,
        "total_updated": total_updated,
        "total_skipped": total_skipped,
    }

