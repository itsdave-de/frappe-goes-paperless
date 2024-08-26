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
         # Create a new supplier
        supplier = frappe.get_doc({
            'doctype': 'Supplier',
            'supplier_name': invoice_details['SupplierName'],
            'supplier_group': '',
            'supplier_type': 'Company'
        })
        supplier.insert()
        print(f"Supplier '{supplier.supplier_name}' created successfully!")
        # supplier = frappe.new_doc('Supplier')
        # supplier.supplier_name = invoice_details['SupplierName']
        # supplier.supplier_group = 'All Supplier Groups'
        # supplier.supplier_type = 'Company'
        # supplier.insert()
        # return_msg = 'Contact created successfully'
    else:
        supplier = frappe.get_doc('Supplier', supplier)
        return_msg = 'Supplier already exists, updated successfully'
    # Update AI Query with supplier
    ai_query_doc = frappe.get_doc('AI Query', doc.get('name'))
    ai_query_doc.supplier = supplier.name
    ai_query_doc.save()
    # commit database
    frappe.db.commit()

    # Create a new contact by json if not exists
    contactPerson = invoice_details.get('ContactPerson')
    if contactPerson:
        contactPerson = contactPerson.split(' ')
    else:
        if invoice_details.get('SupplierName'):
            contactPerson = invoice_details['SupplierName'].split(' ')
        else:
            contactPerson = ['Unknown', 'Unknown']
    contact = frappe.db.get_value(
        'Contact', 
        {
            'first_name': contactPerson[0],
            'last_name': contactPerson[1] if len(contactPerson) > 1 else ''
        }
    )
    if not contact:
        contact = frappe.new_doc('Contact')
        contact.first_name = contactPerson[0]
        contact.last_name = contactPerson[1] if len(contactPerson) > 1 else ''
        contact.phone = invoice_details['ContactPhone'] if invoice_details.get('ContactPhone') else ''
        contact.append('links', {
            'link_doctype': 'Supplier',
            'link_name': supplier.name
        })
        contact.insert()
    else:
        contact = frappe.get_doc('Contact', contact)
        check_exists = [s for s in contact.links if s.link_name == supplier.name]
        if not check_exists:
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
        check_exists = [s for s in address.links if s.link_name == supplier.name]
        if not check_exists:
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
    print(supplier)
    if not supplier:
        frappe.throw(f"Supplier does not exist.")
    supplier_doc = frappe.get_doc('Supplier', supplier)

    invoice_details = json_data.get('InvoiceDetails')
    items_purchased = json_data['ItemsPurchased']['ItemList']
    financial_summary = json_data['FinancialSummary']
    payment_information = json_data['PaymentInformation']

    # Create if not exists
    purchase_invoice_list = frappe.get_all(
        'Purchase Invoice', filters= {"bill_no": invoice_details['InvoiceNumber']}
    )
    if len(purchase_invoice_list) == 0:
         # Create a Purchase Invoice
        purchase_invoice = frappe.get_doc({
            'doctype': 'Purchase Invoice',
            'supplier': supplier_doc.name,
            'posting_date': invoice_details['InvoiceDate'],
            'due_date': payment_information['PaymentDueDate'],
            'bill_no': invoice_details['InvoiceNumber'],
            'bill_date': invoice_details['InvoiceDate'],
            'items': []
        })
        
    else:
        purchase_invoice = frappe.get_doc('Purchase Invoice', purchase_invoice_list[0].name)

    # Adiciona os itens ao Purchase Invoice
    items = []
    for item in items_purchased:
        item_doc_name = create_item(item['ItemNumber'], item['Description'], supplier)
        item_doc = frappe.get_doc("Item", item_doc_name)
        po_item = create_purchase_invoice_doc_item(item_doc.name,float(item["Quantity"]), item_doc.stock_uom, float(item["UnitPrice"]))
        items.append(po_item)
    
    #Append Items to PI
    purchase_invoice.append('items', items)
        

    # Definy the total and tax amount
    purchase_invoice.total = financial_summary['TotalNetAmount']
    purchase_invoice.total_taxes_and_charges = sum(
        tax['Amount'] for tax in financial_summary['VAT/TAXBreakdown']['VAT/TAXList']
    )

    # Define the write off amount
    #purchase_invoice.base_grand_total = purchase_invoice.base_grand_total if not None else 0.0

    # save data
    purchase_invoice.save()
    frappe.db.commit()

def get_country(code_country):
    # Get country by code
    country = frappe.db.get_value('Country', {'code': code_country.lower()})
    return country

def create_item(item_code, item_name, supplier, item_group='All Item Groups', stock_uom='Stk'):

	# Check if the item already exists
    if not frappe.db.exists('Item', item_code):
        # Create a new item
        item = frappe.get_doc({
            'doctype': 'Item',
            'item_code': item_code,
            'item_name': item_code,
            "description":item_name,
            'item_group': item_group,
            'stock_uom': stock_uom,
            "default_supplier": supplier,
            'is_stock_item': 1,  # Set as a stock item
            'include_item_in_manufacturing': 0
        })
        item.insert()
        frappe.db.commit()
        print(f"Item '{item_code}' created successfully!")
        return item.name
    else:
        print(f"Item '{item_code}' already exists.")
        return frappe.get_doc("Item",item_code).name

def create_purchase_invoice_doc_item(item_code, qty, uom, rate ):
    return frappe.get_doc({
        "doctype": "Purchase Invoice Item",
        "item_code": item_code,
        "item_name": item_code,
        "qty": qty,
        "uom": uom,
        "rate": rate,
        "amount":qty*rate
    })