import frappe
from frappe import _

def get_data():
    if 'ai_workflows' in frappe.get_installed_apps():
        return {
            'heatmap': False,
            'heatmap_message': _('Based on AI queries of linked Document.'),
            'fieldname': 'paperless_doc',
            'transactions': [
                {
                    'label': _('Available AI Queries'),
                    'items': ['AI Query']
                }
            ]
        }