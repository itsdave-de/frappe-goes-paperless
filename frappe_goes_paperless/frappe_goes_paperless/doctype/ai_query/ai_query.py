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

	# Create a new contact by json
	contact = frappe.new_doc('Contact')
	contact.first_name = json_data['ContactPerson'].split(' ')[0]
	contact.last_name = json_data['ContactPerson'].split(' ')[1]
	contact.phone = json_data['ContactPhone']
	contact.save()

	# Create a new address by json
	address = frappe.new_doc('Address')
	address.address_line1 = json_data['SupplierAddress']['Street']
	address.city = json_data['SupplierAddress']['City']
	address.pincode = json_data['SupplierAddress']['PostalCode']
	address.country = json_data['SupplierAddress']['Country']
	address.save()

	# Create a new supplier by json
	supplier = frappe.new_doc('Supplier')
	supplier.supplier_name = json_data['SupplierName']
	supplier.contact = contact.name
	supplier.address = address.name
	supplier.save()

	return 'Supplier created successfully'