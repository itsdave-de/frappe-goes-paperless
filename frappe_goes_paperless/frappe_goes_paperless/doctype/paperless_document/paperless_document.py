# Copyright (c) 2024, itsdave GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
from frappe.utils.background_jobs import get_job_status
import requests
import re
import json
from openai import OpenAI


def get_paperless_settings():
    settings = frappe.get_doc('Paperless-ngx Settings', 'Paperless-ngx Settings')
    api_token = get_decrypted_password(
        doctype='Paperless-ngx Settings',
        name='Paperless-ngx Settings',
        fieldname='api_token',
        raise_exception=False
    )
    return settings.paperless_ngx_server, api_token

def get_ai_settings(doc_ai):
    doc_ai = frappe.get_doc('AI', doc_ai)

    api_key = get_decrypted_password(
        doctype ='AI',
        name = doc_ai.name,
        fieldname = 'api_key',
        raise_exception=False
    )
    return api_key

def get_paperless_fulltext(document_id):
    server_url, api_token = get_paperless_settings()
    response = requests.get(
        f"{server_url.rstrip('/')}/api/documents/{document_id}/",
        headers = {
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json"
        }
    )
    if response.status_code == 200:
        if len(response.json()) > 0:
            return response.json()['content']
    return None


def get_paperless_ids():
    server_url, api_token = get_paperless_settings()
    response = requests.get(
        f"{server_url.rstrip('/')}/api/documents/",
        headers = {
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json"
        }
    )
    if response.status_code == 200:
        if len(response.json()) > 0:
            return response.json()['all']
    return None

# Get document thumbprint image
def get_paperless_docthumb(id, docname):
    server_url, api_token = get_paperless_settings()
    response = requests.get(
        f"{server_url.rstrip('/')}/api/documents/{id}/thumb/",
        headers = {
            "Authorization": f"Token {api_token}"
        }
    )
    if response.status_code == 200:
        if response.content:
            file_doc = frappe.new_doc("File")
            file_doc.file_name = f"docthumb-{id}.webp"
            file_doc.attached_to_doctype = 'Paperless Document'
            file_doc.attached_to_name = docname
            file_doc.content = response.content
            file_doc.decode = False
            file_doc.is_private = False
            file_doc.insert(ignore_permissions=True)
            frappe.db.commit()
            return file_doc.file_url
    return None

# Get data from paperless-ngx
def paperless_api(place, id):
    server_url, api_token = get_paperless_settings()
    response = requests.get(
        f"{server_url.rstrip('/')}/api/{place}/{id}/",
        headers = {
            "Authorization": f"Token {api_token}",
            "Content-Type": "application/json"
        }
    )
    if response.status_code == 200:
        if len(response.json()) > 0:
            return response.json()
    return None


class PaperlessDocument(Document):
    pass


@frappe.whitelist()
def button_get_ai(doc):
    print('Starting function to get ai ...')
    jobId = frappe.enqueue(
        'frappe_goes_paperless.frappe_goes_paperless.doctype.paperless_document.paperless_document.get_ai_data',
        queue = 'short',
        now = False,
        self = doc
    )
    return jobId.id


@frappe.whitelist()
def job_status(jobid):
    getStatus = None
    getJob = [(j.job_id, j.status) for j in frappe.get_all('RQ Job', filters={'job_id': jobid}) if j.job_id == jobid]
    if len(getJob) > 0:
        for job_id, status in getJob:
            if job_id == jobid:
                getStatus = status
                break
    return getStatus


@frappe.whitelist()
def call_ai(ai, prompt, doc, background=True):
    # Universal AI
    print('Starting function to get ai ...')
    if background == 'false':
        background = False
    # Get AI
    try:
        doc_ai = frappe.get_doc('AI', ai)
    except frappe.DoesNotExistError:
        return 'AI not found!'
    # Check if AI is OpenAI
    print(doc)
    # {"ai":"AI-00001","ai_prompt":"AIPROMPT-00001"}
    print(doc_ai.interface)
    # openAI
    print(background)
    # false (string)
    if doc_ai.interface == 'openAI':
        if background:
            jobId = frappe.enqueue(
                'frappe_goes_paperless.frappe_goes_paperless.doctype.paperless_document.paperless_document.use_openai',
                queue = 'short',
                now = False,
                doc = doc,
                prompt = prompt,
                ai_config = doc_ai.name,
                background = True
            )
            return jobId
        else:
            do_ai = use_openai(doc, prompt, doc_ai.name, False)
            if do_ai:
                return do_ai


def use_openai(doc, prompt, ai_name, background=True):
    print('Initiate get ai data ...')

    client = OpenAI(api_key = get_ai_settings(ai_name))
    doc = json.loads(doc)

    # get prompt
    prompt = frappe.get_doc("AI Prompt", doc.get('ai_prompt'), fields=['long_text_fnbe', 'for_doctype'])
    # concat fulltext and prompt
    effective_prompt = f"{doc.get('document_fulltext')}\n\n{prompt.long_text_fnbe}"
    # init chat
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": effective_prompt,
            }
        ],
        model="chatgpt-4o-latest",
    )
    if chat_completion.choices:
        resp = chat_completion.choices[0].message.content
    else:
        resp = ""
    # add doctype AI Query
    new_query = frappe.new_doc("AI Query")
    new_query.document_type = prompt.for_doctype
    new_query.ai = ai_name
    new_query.ai_prompt_template = doc.get('ai_prompt')
    new_query.effective_prompt = effective_prompt
    new_query.ai_response = resp.strip() if resp else ""
    
    json_pattern = r'\{.*\}'
    if resp is not None:
        matches = re.findall(json_pattern, resp, re.DOTALL)
    else:
        matches = []
    if matches:
        json_content = matches[0]
        try:
            data = json.loads(json_content)
            formatted_json = json.dumps(data, indent=2)
            new_query.ai_response_json = formatted_json
        except json.JSONDecodeError as e:
            new_query.ai_response_json = f"Error on decode JSON: {e}"
    else:
        new_query.ai_response_json = 'The content is not in JSON format'
    # save query ai
    new_query.save()
    # Load document paperless and set status
    doc_paperless = frappe.get_doc("Paperless Document", doc.get('name'))
    doc_paperless.status = 'AI-Response-Recieved'
    doc_paperless.save()
    frappe.db.commit()
    # Return success
    if background:
        frappe.publish_realtime('msgprint_end', 'Response received successfully, fields updated!')
        return True
    else:
        return 'Response received successfully, fields updated!'


@frappe.whitelist()
def sync_documents():
    # Get all ids from paperless
    ids = get_paperless_ids()
    # get all ids from frappe
    docs = frappe.get_all('Paperless Document', fields=['paperless_document_id'])
    # Get a array with missing ids (compare the two lists of ids)
    mis = list(set(ids) - set([int(id['paperless_document_id']) for id in docs if id.get('paperless_document_id') is not None]))
    for id in mis:
        try:
            get_document = paperless_api('documents', id)
            # Get frappe doctype by Paperless doctype
            response = paperless_api('document_types', get_document['document_type'])
            if response is not None:
                paperless_doctype = response['name']
            else:
                paperless_doctype = None
            paperless_doctype = paperless_doctype['name'] if paperless_doctype else None
            frappe_doctype = frappe.get_all(
                'Paperless Document Type Mapping',
                fields = ['frappe_doctype'],
                filters = {'paperless_document_type': paperless_doctype}
            )
            frappe_doctype = frappe_doctype[0]['frappe_doctype'] if len(frappe_doctype) > 0 else None
            # Get prompt from frappe doctype
            frappe_prompt = frappe.get_all(
                'AI Prompt',
                fields = ['name'],
                filters = {'for_doctype': frappe_doctype}
            )
            frappe_prompt = frappe_prompt[0]['name'] if len(frappe_prompt) > 0 else None
            # add document
            new_doc = frappe.new_doc("Paperless Document")
            new_doc.paperless_document_id = id
            new_doc.paperless_correspondent = paperless_api('correspondents', get_document['correspondent'])['name']
            new_doc.paperless_documenttype = paperless_doctype
            new_doc.status = "new"
            new_doc.frappe_doctype = frappe_doctype
            new_doc.ai_prompt = frappe_prompt
            new_doc.document_fulltext = get_document['content']
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
