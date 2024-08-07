# Copyright (c) 2024, itsdave GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests


class PaperlessngxSettings(Document):
    @frappe.whitelist()
    def sync_suppliers(self):
        sync_suppliers()

    @frappe.whitelist()
    def sync_customers(self):
        sync_customers()


def get_paperless_settings():
    settings = frappe.get_single('Paperless-ngx Settings')
    return settings.paperless_ngx_server, settings.api_token

@frappe.whitelist()
def sync_customers():
    server_url, api_token = get_paperless_settings()
    customers = frappe.get_all('Customer', fields=['name', 'customer_name'])

    for customer in customers:
        correspondent_name = f"{customer.customer_name} {customer.name}"
        data = {
            "name": correspondent_name,
            "match": "",
            "matching_algorithm": 6,
            "owner": 3,
            "is_insensitive": False,
        }

        response = requests.post(
            f"{server_url}/api/correspondents/",
            json=data,
            headers={
                "Authorization": f"Token {api_token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 201:
            # Mark sync field
            frappe.db.set_value('Customer', customer.name, 'custom_synced_to_paperlessngx', 1)
            frappe.msgprint(f"Synced: {correspondent_name}")
        else:
            frappe.msgprint(f"Error on sync customer {customer.name}: {response.text}")
            
@frappe.whitelist()
def sync_suppliers():
    server_url, api_token = get_paperless_settings()
    suppliers = frappe.get_all('Supplier', fields=['name', 'supplier_name'])

    for supplier in suppliers:
        correspondent_name = f"{supplier.supplier_name} {supplier.name}"
        data = {
            "name": correspondent_name,
            "match": "",
            "matching_algorithm": 6,
            "owner": 3,
            "is_insensitive": False,
        }

        response = requests.post(
            f"{server_url}/api/correspondents/",
            json=data,
            headers={
                "Authorization": f"Token {api_token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code == 201:
            # Mark sync field
            frappe.db.set_value('Supplier', supplier.name, 'custom_synced_to_paperlessngx', 1)
            frappe.msgprint(f"Synced: {correspondent_name}")
        else:
            frappe.msgprint(f"Error on sync supplier {supplier.name}: {response.text}")
