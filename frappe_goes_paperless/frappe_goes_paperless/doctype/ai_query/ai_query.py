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
        if not contact.links.get('link_name') == supplier.name:
            contact.append('links', {
                'link_doctype': 'Supplier',
                'link_name': supplier.name
            })
            contact.save()
    # assign contact to supplier
    supplier.supplier_primary_contact = contact.name
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
        if not address.links.get('link_name') == supplier.name:
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


@frappe.whitelist()
def create_purchase_invoice(doc):
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
    
    # Get suppiler
    supplier = frappe.db.get_value(
        'Supplier',
        {
            'name': doc.get('supplier')
        }
    )
    print(doc)
    print(supplier)
    if not supplier:
        frappe.throw(f"Supplier does not exist.")
    supplier_doc = frappe.get_doc('Supplier', supplier)

    invoice_details = json_data.get('InvoiceDetails')
    items_purchased = json_data['ItemsPurchased']['ItemList']
    financial_summary = json_data['FinancialSummary']
    payment_information = json_data['PaymentInformation']

    # Create if not exists
    purchase_invoice = frappe.db.get_value(
        'Purchase Invoice',
        {
            'bill_no': invoice_details['InvoiceNumber']
        }
    )
    if not purchase_invoice:
        purchase_invoice = frappe.new_doc('Purchase Invoice')
        purchase_invoice.supplier = supplier_doc.name
        purchase_invoice.posting_date = invoice_details['InvoiceDate']
        purchase_invoice.due_date = payment_information['PaymentDueDate']
        purchase_invoice.bill_no = invoice_details['InvoiceNumber']
        purchase_invoice.bill_date = invoice_details['InvoiceDate']
        #purchase_invoice.credit_to = 'Creditors - ACC'
    else:
        purchase_invoice = frappe.get_doc('Purchase Invoice', purchase_invoice)

    # Adiciona os itens ao Purchase Invoice
    for item in items_purchased:
        if not item['ItemNumber']:
            purchase_invoice.append('items', {
                'item_code': item['ItemNumber'],
                'item_name': item['Description'],
                'qty': item['Quantity'],
                'rate': item['UnitPrice'],
                'amount': item['Total'],
                'uom': 'Nos'
            })

    # Definy the total and tax amount
    purchase_invoice.total = financial_summary['TotalNetAmount']
    purchase_invoice.total_taxes_and_charges = sum(
        tax['Amount'] for tax in financial_summary['VAT/TAXBreakdown']['VAT/TAXList']
    )

    # save data
    purchase_invoice.save()
    frappe.db.commit()

def get_country(code_country):
    # Get country by code
    country = frappe.db.get_value('Country', {'code': code_country.lower()})
    return country
