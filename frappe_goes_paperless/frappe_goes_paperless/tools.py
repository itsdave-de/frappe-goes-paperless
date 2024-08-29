# Copyright (c) 2024, itsdave GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.password import get_decrypted_password
import requests


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
