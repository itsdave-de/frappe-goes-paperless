frappe.listview_settings['Paperless Document'] = {
    get_indicator: function(doc) {
        if (doc.status === "new") {
            return [__("new"), "red", "status,=,new"];
        } else if (doc.status === "AI-Response-Received") {
            return [__("AI-Response-Received"), "yellow", "status,=,AI-Response-Received"];
        } else if (doc.status === "Workflow Successful") {
            return [__("Workflow Successful"), "green", "status,=,Workflow Successful"];
        } else if (doc.status === "Destination Document Cancelled") {
            return [__("Destination Document Cancelled"), "red", "status,=,Destination Document Cancelled"];
        }
    }
};
