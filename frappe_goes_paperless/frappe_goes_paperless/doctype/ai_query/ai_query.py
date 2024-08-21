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

	# Create a new supplier by json if not exists and save to edit
	supplier = frappe.db.get_value(
		'Supplier',
		{
			'supplier_name': invoice_details['SupplierName']
		}
	)
	if not supplier:
		supplier = frappe.new_doc('Supplier')
		supplier.supplier_name = invoice_details['SupplierName']
		supplier.supplier_group = 'All Supplier Groups'
		supplier.supplier_type = 'Company'
		supplier.insert()
		return_msg = 'Contact created successfully'
	else:
		supplier = frappe.get_doc('Supplier', supplier)
		return_msg = 'Contact already exists, updated successfully'

	# Create a new contact by json if not exists
	contact = frappe.db.get_value(
		'Contact', 
		{
			'first_name': invoice_details['ContactPerson'].split(' ')[0],
			'last_name': invoice_details['ContactPerson'].split(' ')[1]
		}
	)
	if not contact:
		contact = frappe.new_doc('Contact')
		contact.first_name = invoice_details['ContactPerson'].split(' ')[0]
		contact.last_name = invoice_details['ContactPerson'].split(' ')[1]
		contact.phone = invoice_details['ContactPhone']
		contact.append('links', {
    		'link_doctype': 'Supplier',
    		'link_name': supplier.name
		})
		contact.insert()
	else:
		contact = frappe.get_doc('Contact', contact)
		contact.links = [
			{
				'link_doctype': 'Supplier',
				'link_name': supplier.name
			}
		]
		contact.save()
	# assign contact to supplier
	supplier.supplier_primary_address = contact.name
	supplier.save()

	# Create a new address by json if not exists
	address = frappe.db.get_value(
		'Address',
		{
			'address_line1': invoice_details['SupplierAddress']['Street'],
			'city': invoice_details['SupplierAddress']['City'],
			'pincode': invoice_details['SupplierAddress']['PostalCode'],
			'country': get_country(invoice_details['SupplierAddress']['Country'])
		}
	)
	if not address:
		address = frappe.new_doc('Address')
		address.address_title = 'Main Address'
		address.address_line1 = invoice_details['SupplierAddress']['Street']
		address.city = invoice_details['SupplierAddress']['City']
		address.pincode = invoice_details['SupplierAddress']['PostalCode']
		address.country = get_country(invoice_details['SupplierAddress']['Country'])
		address.append('links', {
			'link_doctype': 'Supplier',
			'link_name': supplier.name
		})
		address.insert()
	else:
		address = frappe.get_doc('Address', address)
		address.append('links', {
			'link_doctype': 'Supplier',
			'link_name': supplier.name
		})
		address.save()
	# assign address to supplier
	supplier.supplier_primary_address = address.name
	supplier.save()

	# commit database and return message
	frappe.db.commit()
	return return_msg


def get_country(code_country):
	# Get country by code
	country = frappe.db.get_value('Country', {'code': code_country.lower()})
	return country
