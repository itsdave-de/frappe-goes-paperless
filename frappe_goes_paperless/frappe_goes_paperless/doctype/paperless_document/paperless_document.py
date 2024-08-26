# Copyright (c) 2024, itsdave GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password
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
    prompt = frappe.get_doc("AI Prompt", prompt)
    # check AI mode
    if prompt.ai_output_mode == 'Structured Output (JSON)':
        effective_prompt = f"{prompt.long_text_fnbe}\n\n{doc.get('document_fulltext')}"
        json_schema = json.loads(prompt.json_scema) if type(prompt.json_scema) == str else prompt.json_scema
        chat_response = client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": "You are a wizard that generates invoice details in JSON format."},
                {"role": "user", "content": effective_prompt}
            ],
            functions=[
                {
                    "name": "generate_invoice",
                    "description": "Generates an invoice based on the provided schema.",
                    "parameters": json_schema
                }
            ],
            function_call={"name": "generate_invoice"}
        )
        if chat_response.choices:
            function_call = chat_response.choices[0].message.function_call
            if function_call:
                resp = function_call.arguments
            else:
                resp = ""
        else:
            resp = ""
    # else if AI mode is Chat or None
    else:
        # concat fulltext and prompt
        effective_prompt = f"{prompt.long_text_fnbe}\n\n{doc.get('document_fulltext')}"
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
    new_query.paperless_doc = doc.get('name')
    new_query.ai = ai_name
    new_query.ai_prompt_template = prompt
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
        return f'AI query sucessfull. <a href="{frappe.utils.get_url()}/app/ai-query/{new_query.name}">Check out response</a>.'


