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

