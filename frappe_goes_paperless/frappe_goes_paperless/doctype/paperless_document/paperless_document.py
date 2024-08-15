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


class PaperlessDocument(Document):
	@frappe.whitelist()
	def get_ai_data(self):
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
			json_content = matches
			try:
				data = json.loads(json_content)
				formatted_json = json.dumps(data, indent=2)
				self.ai_response_json = formatted_json
			except json.JSONDecodeError as e:
				print("Error on decode JSON:", e)
		else:
			self.ai_response_json = 'Content not is a json format'
		self.save()
