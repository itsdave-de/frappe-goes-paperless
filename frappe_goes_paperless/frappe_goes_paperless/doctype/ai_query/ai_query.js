// Copyright (c) 2024, itsdave GmbH and contributors
// For license information, please see license.txt

// frappe.ui.form.on("AI Query", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("AI Query", {
    refresh: function(frm) {
        frm.add_custom_button(__('Create Supplier'), () => {
            frappe.call({
                method: 'frappe_goes_paperless.frappe_goes_paperless.doctype.ai_query.ai_query.create_supplier',
                args: {
                    doc: frm.doc
                },
                callback: function(r) {
                    if (r.message) {
                        // Display the response as a message
                        frappe.msgprint(r.message);
                        frappe.refresh_field('supplier');
                    } else {
                        frappe.msgprint(__('No response received.'));
                    }
                },
                error: function() {
                    // Unfreeze the screen in case of error
                    //frappe.unfreeze();
                },
                freeze: true,
                freeze_message: 'Creating Supplier...'
            });
        }, __("Workflow"));
        frm.add_custom_button(__('Create Purchase Invoice'), () => {
            frappe.call({
                method: 'frappe_goes_paperless.frappe_goes_paperless.doctype.ai_query.ai_query.create_purchase_invoice',
                args: {
                    doc: frm.doc
                },
                callback: function(r) {
                    if (r.message) {
                        // Display the response as a message
                        frappe.msgprint(r.message);
                    } else {
                        frappe.msgprint(__('No response received.'));
                    }
                },
                error: function() {
                    // Unfreeze the screen in case of error
                    //frappe.unfreeze();
                },
                freeze: true,
                freeze_message: 'Creating Purchase Invoice...'
            });
        }, __("Workflow"));
    }
});

