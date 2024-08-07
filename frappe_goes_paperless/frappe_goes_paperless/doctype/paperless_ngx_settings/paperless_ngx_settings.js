// Copyright (c) 2024, itsdave GmbH and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Paperless-ngx Settings", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Paperless-ngx Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Sync Suppliers to Correspondents'), function() {
            frappe.call({
                method: "sync_suppliers",
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                }
            });
        });
        frm.add_custom_button(__('Sync Suppliers to Sync Customers to Correspondents'), function() {
            frappe.call({
                method: "sync_customers",
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                }
            });
        });
    }
});