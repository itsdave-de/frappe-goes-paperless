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

def get_ai_settings():
    api_key = get_decrypted_password(
        doctype='AI Settings',
        name='AI Settings',
        fieldname='api_key',
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
	#frappe.show_alert('Starting query in AI...')
	frappe.enqueue(get_ai_data, queue='short', self=doc)


def get_ai_data(self):
	print('Initiate get ai data ...')
	frappe.publish_realtime('msgprint', 'Starting query in AI...')

	client = OpenAI(api_key = get_ai_settings())

	# get prompt
	prompt = frappe.get_doc("AI Prompt", self.get('ai_prompt'), fields=['long_text_fnbe'])
	# concat fulltext and prompt
	prompt = f"{get_paperless_fulltext(self.get('paperless_document_id'))}\n\n{prompt.long_text_fnbe}"
	# init chat
	chat_completion = client.chat.completions.create(
		messages=[
			{
				"role": "user",
				"content": prompt,
			}
		],
		model="chatgpt-4o-latest",
	)
	resp = chat_completion.choices[0].message.content.strip()
	self.ai_response = resp
	json_pattern = r'\{.*\}'
	matches = re.findall(json_pattern, resp, re.DOTALL)
	if matches:
		json_content = matches[0]
		try:
			data = json.loads(json_content)
			formatted_json = json.dumps(data, indent=2)
			self.ai_response_json = formatted_json
		except json.JSONDecodeError as e:
			self.ai_response_json = f"Error on decode JSON: {e}"
	else:
		self.ai_response_json = 'The content is not in JSON format'
	self.status = 'AI-Response-Recieved'
	self.save()
	frappe.publish_realtime('msgprint', 'Response received successfully, fields updated!')
	print('Response received successfully, fields updated!')


@frappe.whitelist()
def sync_documents():
	# Get all ids from paperless
	ids = get_paperless_ids()
	# get all ids from frappe
	docs = frappe.get_all('Paperless Document', fields=['paperless_document_id'])
	# Get a array with missing ids (compare the two lists of ids)
	mis = list(set(ids) - set([int(id['paperless_document_id']) for id in docs]))
	for id in mis:
		try:
			get_document = paperless_api('documents', id)
			# Get frappe doctype by Paperless doctype
			paperless_doctype = paperless_api('document_types', get_document['document_type'])['name']
			frappe_doctype = frappe.get_all(
				'Paperless Document Type Mapping',
				fields = ['frappe_doctype'],
				filters = {'paperless_document_type': paperless_doctype}
			)
			if len(frappe_doctype) > 0:
				frappe_doctype = frappe_doctype[0]['frappe_doctype']
			else:
				frappe_doctype = None
			# Get prompt from frappe doctype
			frappe_prompt = frappe.get_all(
				'AI Prompt',
				fields = ['name'],
				filters = {'for_doctype': frappe_doctype}
			)
			if len(frappe_prompt) > 0:
				frappe_prompt = frappe_prompt[0]['name']
			else:
				frappe_prompt = None
			# add document
			new_doc = frappe.get_doc({
				"doctype": "Paperless Document",
				"paperless_document_id": id,
				"paperless_correspondent": paperless_api('correspondents', get_document['correspondent'])['name'],
				"paperless_documenttype": paperless_doctype,
				"status": "new",
				"frappe_doctype": frappe_doctype,
				"ai_prompt": frappe_prompt
			})
			new_doc.insert()
			frappe.db.commit()
			print(f"Document added -> {get_document['title']}")
		except Exception as e:
			# Handle HTTP errors
			frappe.log_error(
				f"Failed to fetch documents from Paperless-ngx: {e}"
			)
