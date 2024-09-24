// Copyright (c) 2024, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Paperless Document", {
    refresh: function (frm) {
        frm.add_custom_button(__('Open document on Paperless'), () => {
            open_document_on_paperless(frm.doc.paperless_document_id);
        }, __("Actions"));

        // Add a click function to open the document in Paperless from the thumbprint preview
        let image_field = frm.fields_dict['thumbprint_preview'].$wrapper.find('img');
        if (image_field.length) {
            image_field.css('cursor', 'pointer');
            image_field.on('click', function () {
                open_document_on_paperless(frm.doc.paperless_document_id);
            });
        }
    }
});

function open_document_on_paperless(document_id) {
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Paperless-ngx Settings',
            name: 'Paperless-ngx Settings',
            fieldname: 'paperless_ngx_server'
        },
        callback: function (response) {
            if (response && response.message && response.message.paperless_ngx_server) {
                let server_url = response.message.paperless_ngx_server.replace(/\/$/, '');
                window.open(server_url + '/documents/' + document_id + '/details', '_blank');
            } else {
                console.error("Paperless-ngx server URL not found.");
            }
        }
    });
}
