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

# Monatsnamen-Datum parsen
def parse_date_with_month_name(raw: str):
    """Versucht Datumsangaben wie '30 Oktober 2025' oder '30 October 2025' zu parsen.
    Gibt ein date-Objekt oder None zurück.
    """
    if not raw:
        return None

    # alles etwas normalisieren
    txt = " ".join(raw.replace("\n", " ").split())
    parts = txt.split(" ")
    if len(parts) < 3:
        return None

    # einfache Annahme: <Tag> <Monatsname> <Jahr>
    # z.B. 30 Oktober 2025 oder 30. Oktober 2025
    try:
        day_str = parts[0].rstrip(".")
        day = int(day_str)
    except Exception:
        return None

    # Monatsname kann an zweiter Stelle sein
    month_word = parts[1].strip().rstrip(".").lower()

    month_map = {
        # Deutsch
        "januar": 1, "jan": 1,
        "februar": 2, "feb": 2,
        "märz": 3, "maerz": 3, "mrz": 3,
        "april": 4, "apr": 4,
        "mai": 5,
        "juni": 6, "jun": 6,
        "juli": 7, "jul": 7,
        "august": 8, "aug": 8,
        "september": 9, "sept": 9, "sep": 9,
        "oktober": 10, "okt": 10,
        "november": 11, "nov": 11,
        "dezember": 12, "dez": 12,
        # Englisch (für Sicherheit)
        "january": 1,
        "february": 2,
        "march": 3,
        "april": 4,
        "may": 5,
        "june": 6,
        "july": 7,
        "august": 8,
        "september": 9,
        "october": 10,
        "november": 11,
        "december": 12,
    }

    month = month_map.get(month_word)
    if not month:
        return None

    # Jahr sollte das letzte Element sein
    try:
        year = int(parts[-1].rstrip("."))
    except Exception:
        return None

    if year < 1900 or year > 2100:
        return None

    try:
        return date(year, month, day)
    except Exception:
        return None

#Hilfsfunktion: Datum aus Volltext extrahieren
# def extract_invoice_date_from_text(text: str):
#     """Versucht, ein Rechnungs-/Quittungsdatum aus dem Volltext zu holen.

#     Strategie:
#     1. Suche nach Keywords wie 'Rechnungsdatum', 'Quittungsdatum' etc. + Datum danach
#     2. Versuche dabei zuerst numerische Datumsformate, dann '30 Oktober 2025' usw.
#     3. Wenn nichts gefunden → global im Text nach dem ersten plausiblen Datum suchen.
#     """

#     if not text:
#         return None

#     # Normalisieren
#     normalized = " ".join(text.replace("\n", " ").split())
#     lower = normalized.lower()

#     # Relevante Keywords, nach denen wir zuerst schauen
#     keywords = [
#         "rechnungsdatum",
#         "quittungsdatum",
#         "invoice date",
#         "belegdatum",
#         "rechnung vom",
#         "datum",
#     ]

#     # Muster: numerische Datumsangaben (01.01.2024, 1-1-24, 01/01/2024)
#     numeric_pattern = re.compile(r"(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})")

#     def _is_plausible(d):
#         # hier kannst du den Bereich einschränken, z.B. ab 2015
#         return d and str(d) >= "2015-01-01"

#     # 1) Versuche zuerst: Keyword + Datum dahinter
#     for kw in keywords:
#         idx = lower.find(kw)
#         if idx == -1:
#             continue

#         # Stück Text nach dem Keyword
#         snippet = normalized[idx:idx + 80]  # 80 Zeichen danach reichen oft
#         snippet_lower = snippet.lower()

#         # 1a) Erst numerisches Datum im Snippet versuchen
#         num_matches = numeric_pattern.findall(snippet)
#         for raw in num_matches:
#             try:
#                 parsed = frappe.utils.parse_date(raw)
#             except Exception:
#                 continue
#             if _is_plausible(parsed):
#                 return parsed

#         # 1b) Dann Datumsangaben mit Monatsnamen wie '30 Oktober 2025'
#         # Suche 'Zahl Wort Zahl' in dem Ausschnitt
#         word_date_matches = re.findall(r"(\d{1,2}\s+[A-Za-zÄÖÜäöüß\.]+\s+\d{4})", snippet)
#         for raw in word_date_matches:
#             parsed = parse_date_with_month_name(raw)
#             if _is_plausible(parsed):
#                 return parsed

#     # 2) Fallback: irgendwo im gesamten Text numerische Daten suchen
#     num_matches = numeric_pattern.findall(normalized)
#     for raw in num_matches:
#         try:
#             parsed = frappe.utils.parse_date(raw)
#         except Exception:
#             continue
#         if _is_plausible(parsed):
#             return parsed

#     # 3) Fallback: irgendwo '30 Oktober 2025'-artige Daten im gesamten Text
#     word_date_matches = re.findall(r"(\d{1,2}\s+[A-Za-zÄÖÜäöüß\.]+\s+\d{4})", normalized)
#     for raw in word_date_matches:
#         parsed = parse_date_with_month_name(raw)
#         if _is_plausible(parsed):
#             return parsed

#     return None



def extract_invoice_date_from_text(text: str):
    """Einfache, robuste Datumserkennung für Rechnungen/Quittungen.

    - bevorzugt 'Rechnungsdatum 02.11.2020'
    - unterstützt dd.mm.yyyy, dd-mm-yyyy, dd/mm/yyyy, ISO und Monatsnamen
    """

    if not text:
        return None

    # Normalisieren
    normalized = " ".join(text.replace("\n", " ").split())
    lower = normalized.lower()

    # Relevante Keywords
    keywords = [
        "rechnungsdatum",
        "quittungsdatum",
        "invoice date",
        "belegdatum",
        "rechnung vom",
        "datum",
    ]

    # Muster
    numeric_pattern = re.compile(r"(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4})")   # 02.11.2020, 02-11-2020
    iso_pattern = re.compile(r"(\d{4}-\d{2}-\d{2})")                     # 2020-11-02
    word_pattern = re.compile(r"(\d{1,2}\s+[A-Za-zÄÖÜäöüß\.]+\s+\d{4})") # 30 Oktober 2025

    def _is_plausible(d):
        return d and str(d) >= "2010-01-01"

    def _parse_loose(raw: str):
        """Versuch 1: frappe.utils.parse_date, Versuch 2: dd.mm.yyyy selber parsen."""
        if not raw:
            return None

        # Erst Frappe probieren
        try:
            d = frappe.utils.parse_date(raw)
            if d:
                return d
        except Exception:
            pass

        # Dann dd.mm.yyyy / dd-mm-yyyy / dd/mm/yyyy selbst parsen
        sep = "." if "." in raw else "-" if "-" in raw else "/" if "/" in raw else None
        if not sep:
            return None

        try:
            day, month, year = raw.split(sep)
            day = int(day)
            month = int(month)
            year = int(year)
            if year < 2000 or year > 2100:
                return None
            return date(year, month, day)
        except Exception:
            return None

    # 1) Keyword + Datum dahinter
    for kw in keywords:
        idx = lower.find(kw)
        if idx == -1:
            continue

        snippet = normalized[idx:idx + 150]

        # 1a) numerisch
        for raw in numeric_pattern.findall(snippet):
            parsed = _parse_loose(raw)
            if _is_plausible(parsed):
                return parsed

        # 1b) ISO
        for raw in iso_pattern.findall(snippet):
            parsed = _parse_loose(raw)
            if _is_plausible(parsed):
                return parsed

        # 1c) Monatsnamen
        for raw in word_pattern.findall(snippet):
            parsed = parse_date_with_month_name(raw)
            if _is_plausible(parsed):
                return parsed

    # 2) Fallback: irgendwo im Text numerische Datumsangaben
    for raw in numeric_pattern.findall(normalized):
        parsed = _parse_loose(raw)
        if _is_plausible(parsed):
            return parsed

    # 3) Fallback: ISO
    for raw in iso_pattern.findall(normalized):
        parsed = _parse_loose(raw)
        if _is_plausible(parsed):
            return parsed

    # 4) Fallback: Monatsnamen
    for raw in word_pattern.findall(normalized):
        parsed = parse_date_with_month_name(raw)
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

