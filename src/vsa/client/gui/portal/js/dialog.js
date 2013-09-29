jQuery(document).ready(function() {
});

function initDialogs() {
	$("#dialog-form").dialog({
			autoOpen: false,
			height: 'auto',
			width: 400,
			modal: true,
			position: 'center',
			buttons: {
				Ok: function() {
					submitDialog();
					//$(this).dialog("close");
				},
				
				Cancel: function() {
					$(this).dialog("close");
				}
			},
			open: function() {
				$('.ui-dialog-buttonpane').find('button').css('width', '80px');
			}
	});

	$("#dialog-msg").dialog({
		resizable: false,
		autoOpen: false,
		height: 'auto',
		width: 400,
		position: 'center',
		modal: true
	});
}

function showFormDialog(title, what, params) {
	var $form = $("#dialog-form");
	$form.html('<span class="loading">loading form...</span>');
	preOpenForm($form, title);
        $.ajaxSetup ({
                cache: false
        });
        var loadUrl = "/vsa/form?form-type="+what;
        $form.html('loading form').load(loadUrl, params,
	  function(response, status, xhr) {
		console.log("showFormDialog status: "+status);
		if (status=="error") {
			showErrorBox("Can't load form");
			$form.dialog("close");
		} else {
			postOpenForm($form,'');
		}
        });
}

function showFormDataDialog(title, data, table) {
	var $form = $("#dialog-form");
	$form.html(data);
	preOpenForm($form, title);
	postOpenForm($form,table);
}

function preOpenForm($form, title) {
	if (!title) { title=$("form", $form).attr("name"); }
	$form.dialog("option", "title", title);
	$form.dialog("option", "width", 400);
	$form.dialog("open");
}

function postOpenForm($form,table) {
	$form.dialog("option","position", "center");
	$form.dialog("option", "height", 'auto');
	$form.data("table", table);
	// radio groups
	var g=jQuery("[id*=group-radio]",$form);
	g.each(function() {
		$(this).contentSwitcher({
			'selector' : ':radio'
		});
	});
}

function submitDialog() {
	var form = $('#ht_form').serializeArray();
	var table = $('#dialog-form').data('table');
	var dialogform = $('#dialog-form');
	console.log('data table: '+table);
	var tableData;
	if (table)
		tableData = serializeTableForm('#manage-table-form');
	var data = form.concat(tableData);

	$.ajax ({
		url: '/vsa/xml/form_submit',
		cache: false,
		type: 'POST',
		data: data,
		dataType: 'xml',
		success: function(data) {
			var response=$(data).find('response').first();
			handleDialogResult(response);
		},
		error: function(xml, text, err) {
			dialogform.dialog('close');
			showErrorBox('submitDialog error: '+text);
		}
	});
	dialogform.html('<span class="loading">Submit in progress...</span>');
}

function handleDialogResult(response) {
	var $form = $('#dialog-form');
	$form.dialog('close');
	var rc = response.attr('rc');
	var refresh = response.attr('refresh');
	var data = response.text();
	var RC_FORM = 2;

	if (rc == 0) {
		// nothing to do
		Alert.info(data);

	} else if (rc == 1) {
		showErrorBox(data);

//	} else if (rc == "msg") {
//		showMessageBox(data);

	} else if (rc == RC_FORM) {
		$form.html(data);
		$form.dialog('open');

	} else {
		console.log('handleDialogResult: unknown rc: '+rc);
	}

	if (refresh == 1)
		refreshTree();
}

function openMessageDialog(title, msg) {
	var $form=$("#dialog-msg");
	var $msg=jQuery("#msg",$form);
	$form.dialog("option", "title", title);
	$form.dialog("option", "buttons", '');
	$msg.html(msg);
	$form.dialog("open");
}

function showErrorBox(msg) {
	$("#dialog-msg > #msg").addClass("ui-state-error");
	openMessageDialog("Error", msg);
}

function showMessageBox(msg) {
	$("#dialog-msg > #msg").removeClass("ui-state-error");
	openMessageDialog("Notice", msg);
}

/*
	func - function to execute on confirmation
*/
function confirmDialog(title, msg, func) {
	var $form=$("#dialog-msg");
	var $msg=jQuery("#msg",$form);
	$msg.removeClass("ui-state-error");
	$form.dialog("option", "title", title);
	buttons = {
		"Ok": function() {
			func();
			$(this).dialog("close");
		},
		Cancel: function() {
			$(this).dialog("close");
		}
	}
	$form.dialog("option", "buttons", buttons);
	var icon='<span class="ui-icon ui-icon-alert" style="float:left; margin:0 7px 20px 0;"></span>';
	$msg.html(icon+msg);
	$form.dialog("open");
	$form.dialog("option","position", "center");
	$form.dialog("option", "height", "auto");
}

function notImplemented() {
	Alert.error("Not Implemented");
}

function addDialog(fpath) {
	var n=getTreeName(fpath);
	showFormDialog("Add "+n, "add", {'form-path': fpath});
}

function editDialog(fpath) {
	console.log("-- editDialog -- "+fpath);
	var n=getTreeName(fpath)
	console.log("-- editDialog -- "+fpath+" : "+n);
	showFormDialog("Edit "+n, "edit", {'form-path': fpath});
}
