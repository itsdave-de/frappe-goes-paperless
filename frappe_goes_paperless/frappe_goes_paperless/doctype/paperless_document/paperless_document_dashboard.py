from frappe import _

def get_data():
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