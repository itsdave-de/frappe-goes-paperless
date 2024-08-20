// Copyright (c) 2024, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Paperless Document", {
    refresh: function(frm) {
        frm.add_custom_button(__('Get AI data'), () => {
            frappe.show_alert('Starting query in AI...');
            frappe.call({
                method: 'frappe_goes_paperless.frappe_goes_paperless.doctype.paperless_document.paperless_document.button_get_ai',
                args: { doc: frm.doc },
                callback: function(response) {
                    if (response.message) {
                        const jobId = response.message;
                        console.log('jobid -> ' + jobId);
                        verificarStatusJob(jobId, frm);
                    }
                }
            });
        }, __("Actions"));
        frm.add_custom_button(__('Open document on Paperless'), () => {
            this.window.open('http://10.251.0.55:8000/documents/' + frm.doc.paperless_document_id + '/details', '_blank');
        }, __("Actions"));

        // Add a custom button named "Query AI"
        frm.add_custom_button(__('Query AI'), function() {
            // Define the Dialog
            let d = new frappe.ui.Dialog({
                title: 'Execute AI Query',
                fields: [
                    {
                        label: 'AI',
                        fieldname: 'ai',
                        fieldtype: 'Link',
                        options: 'AI',  // The Doctype to link to
                        reqd: 1
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
                primary_action: function(data) {

                    // Call the server-side method
                    frappe.call({
                        method: 'frappe_goes_paperless.frappe_goes_paperless.doctype.paperless_document.paperless_document.call_ai',
                        args: {
                            ai: data.ai,
                            prompt: data.ai_prompt,
                            doc: frm.doc,
                            background: false
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

function verificarStatusJob(jobId, frm) {
    frappe.call({
        method: "frappe_goes_paperless.frappe_goes_paperless.doctype.paperless_document.paperless_document.job_status",
        args: {
            jobid: jobId
        },
        callback: function(response) {
            if (response.message) {
                const status = response.message;
                console.log('Job status -> ' + status);
                if (status === "finished") {
                    frappe.show_alert('Response received successfully, fields updated!')
                    frm.refresh_fields();
                } else if (status === "failed") {
                    frappe.msgprint(__('The job is failed'));
                } else {
                    setTimeout(function() {
                        verificarStatusJob(jobId);
                    }, 5000);
                }
            }
        }
    });
}

