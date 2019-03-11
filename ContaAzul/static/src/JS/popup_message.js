odoo.define('ContaAzul.client_actions', function(require){
"user strict";

var core = require('web.core');
var Dialog = require('web.Dialog');

function conta_dialog(parent, action)
{
    var values = action.values || {},

    title = values.title || "Notification",
    sub_title = values.sub_title || "",
    message = values.message || "DONE";

    var dialog = new Dialog(document.body, {
        title: title,
        subtitle: sub_title,
        size: 'medium',
        $content: "<div id='conta_dialog'>" + message + "</div>",
        buttons: []
    });

    dialog.open();
}

    core.action_registry.add("conta_dialog", conta_dialog);
});