// Copyright (c) 2024, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Paperless Document", {
    refresh: function(frm) {
        frm.get_field('get_ai_data').onclick = function() {
            frappe.show_alert('Starting query in AI...');
            frappe.call({
                method: 'frappe_goes_paperless.frappe_goes_paperless.doctype.paperless_document.paperless_document.button_get_ai',
                args: { doc: frm.doc },
            });
        };
    }
});

