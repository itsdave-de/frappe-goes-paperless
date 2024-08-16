// Copyright (c) 2024, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("Paperless Document", {
    refresh: function(frm) {
        frm.get_field('get_ai_data').onclick = function() {
            frappe.show_alert('Starting query in AI...');
            frappe.call({
                method: 'frappe_goes_paperless.frappe_goes_paperless.doctype.paperless_document.paperless_document.button_get_ai',
                args: { doc: frm.doc },
                callback: function(response) {
                    if (response.message) {
                        const jobId = response.message;
                        console.log('jobid -> ' + jobId);
                        verificarStatusJob(jobId);
                    }
                }
            });
        };
    }
});

function verificarStatusJob(jobId) {
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
                    location.reload();
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

frappe.realtime.on('msgprint_end', (data) => {
    frappe.show_alert(data);
});
