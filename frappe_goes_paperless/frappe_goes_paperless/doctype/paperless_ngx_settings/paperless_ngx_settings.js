// Copyright (c) 2024, itsdave GmbH and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Paperless-ngx Settings", {
// 	refresh(frm) {

// 	},
// });

frappe.ui.form.on('Paperless-ngx Settings', {
    refresh: function(frm) {
        frm.fields_dict['sync_suppliers_to_correspondents'].df.onclick = function() {
            frappe.call({
                method: "sync_suppliers",
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                }
            });
        };
        frm.fields_dict['sync_customers_to_correspondents'].df.onclick = function() {
            frappe.call({
                method: "sync_customers",
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint(r.message);
                    }
                }
            });
        };
    }
});