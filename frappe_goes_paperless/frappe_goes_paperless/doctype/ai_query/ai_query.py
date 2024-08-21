# Copyright (c) 2024, itsdave GmbH and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import json


class AIQuery(Document):
	pass

@frappe.whitelist()
def create_supplier(doc):
	doc = json.loads(doc)

	# json data
	json_data = doc.get('ai_response_json')
	# Check if json_data is a string and have a json format
	if not isinstance(json_data, str):
		return 'Invalid JSON format'
	try:
		json_data = json.loads(json_data)
	except:
		return 'Invalid JSON format'
	
	# json_data example
	#
	# "ContactPerson": "Thorsten Bulk",
    # "ContactPhone": "(0 54 71) 8 06-455",
    # "SupplierName": "MICHAELTELECOM AG",
    # "SupplierAddress": {
    #   "Street": "Bruchheide 34",
    #   "City": "Bohmte",
    #   "PostalCode": "49163",
    #   "Country": "DE"
    # }

	invoice_details = json_data.get('InvoiceDetails')

	# Create a new contact by json
	contact = frappe.new_doc('Contact')
	contact.first_name = invoice_details['ContactPerson'].split(' ')[0]
	contact.last_name = invoice_details['ContactPerson'].split(' ')[1]
	contact.phone = invoice_details['ContactPhone']
	contact.save()

	# Create a new address by json
	address = frappe.new_doc('Address')
	address.address_line1 = invoice_details['SupplierAddress']['Street']
	address.city = invoice_details['SupplierAddress']['City']
	address.pincode = invoice_details['SupplierAddress']['PostalCode']
	address.country = get_country(invoice_details['SupplierAddress']['Country'])
	address.save()

	# Create a new supplier by json
	supplier = frappe.new_doc('Supplier')
	supplier.supplier_name = invoice_details['SupplierName']
	supplier.contact = contact.name
	supplier.address = address.name
	supplier.save()

	return 'Supplier created successfully'


def get_country(code_country):
	# Get country by code
	country = frappe.get_doc('Country', code_country.lower())
	return country.name
