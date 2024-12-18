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

        // Add a custom button named "Query AI" if app AI Flow is installed
        frappe.call({
            method: 'frappe_goes_paperless.frappe_goes_paperless.tools.installed_apps',
            callback: function (response) {
                const installed_apps = response.message;

                if (installed_apps.includes('ai_workflows')) {
                    // Fetch the default AI from AI Settings
                    frappe.call({
                        method: 'frappe.client.get_value',
                        args: {
                            doctype: 'AI Settings',
                            fieldname: 'default_ai'
                        },
                        callback: function (ai_response) {
                            const default_ai = ai_response.message ? ai_response.message.default_ai : null;

                            // add a custom button to the form to execute an AI query
                            frm.add_custom_button(__('Query AI'), function () {
                                // Define the Dialog
                                let d = new frappe.ui.Dialog({
                                    title: 'Execute AI Query',
                                    fields: [
                                        {
                                            label: 'AI',
                                            fieldname: 'ai',
                                            fieldtype: 'Link',
                                            options: 'AI',  // The Doctype to link to
                                            reqd: 1,
                                            default: default_ai  // Preselect the default AI
                                        },
                                        {
                                            label: 'AI Prompt',
                                            fieldname: 'ai_prompt',
                                            fieldtype: 'Link',
                                            options: 'AI Prompt',  // The Doctype to link to
                                            reqd: 1
                                        }
                                    ],
                                    primary_action_label: 'Execute AI Query',
                                    primary_action: function (data) {

                                        // Call the server-side method
                                        frappe.call({
                                            method: 'ai_workflows.ai_workflows.doctype.ai_query.ai_query.call_ai',
                                            args: {
                                                ai: data.ai,
                                                prompt: data.ai_prompt,
                                                doc: frm.doc,
                                                background: false
                                            },
                                            callback: function (r) {
                                                if (r.message) {
                                                    // Display the response as a message
                                                    frappe.msgprint(r.message);
                                                    frm.reload_doc();
                                                } else {
                                                    frappe.msgprint(__('No response received.'));
                                                }
                                            },
                                            error: function () {
                                                // Unfreeze the screen in case of error
                                                //frappe.unfreeze();
                                            },
                                            freeze: true,
                                            freeze_message: 'Executing AI Query...'
                                        });

                                        // Close the dialog
                                        d.hide();
                                    }
                                });

                                // Show the dialog
                                d.show();
                            });
                        }
                    });
                }
            }
        });
    }
});

function verificarStatusJob(jobId, frm) {
    frappe.call({
        method: "frappe_goes_paperless.frappe_goes_paperless.doctype.tools.job_status",
        args: {
            jobid: jobId
        },
        callback: function (response) {
            if (response.message) {
                const status = response.message;
                console.log('Job status -> ' + status);
                if (status === "finished") {
                    frappe.show_alert('Response received successfully, fields updated!')
                    frm.refresh_fields();
                } else if (status === "failed") {
                    frappe.msgprint(__('The job is failed'));
                } else {
                    setTimeout(function () {
                        verificarStatusJob(jobId, frm);
                    }, 5000);
                }
            }
        }
    });
}

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
