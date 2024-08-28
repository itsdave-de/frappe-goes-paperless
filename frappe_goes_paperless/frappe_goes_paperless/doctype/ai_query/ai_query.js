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
                        frm.reload_doc();
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
                        // Assuming the server returns the name of the created Purchase Invoice
                        const purchase_invoice_name = r.message;

                        // Navigate to the Purchase Invoice using frappe.set_route
                        frappe.msgprint(__('Purchase Invoice created. Redirecting...'));
                        frappe.set_route('Form', 'Purchase Invoice', purchase_invoice_name);

                        // Optionally, you can reload the form if needed
                        frm.reload_doc();
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
