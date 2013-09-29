jQuery(document).ready(function() {
});

function initToolbars() {
    initTreeToolbar();
}

function initTreeToolbar() {
    $("#toolbar_tree button").each(function() {
        var icon = "ui-icon-" + $(this).attr('id');
        $(this).button({icons: {primary: icon},text: false});
    });
}

function loadToolbarButtons(what, where, table) {
	$(where).html('<div class="loading">loading buttons</div>');
	$.ajax ({
		url: "/vsa/xml/buttons",
		cache: false,
		type: 'GET',
		data: {'path':what},
		dataType: 'xml',
		success: function(data) {
			var response = $(data).find('response').first();
			initToolbarButtons(where, table, response);
                },
                error: function(xml, text, err) {
			$(where).html(errorDiv("Can't load toolbar buttons"));
		}
	});
}

function initToolbarButtons(id, table, response) {
	console.log('--- init toolbar buttons ---- '+id);
	console.log(response);
	//var h='';
	$(id).empty();
	var rc = response.attr('rc');
	if (rc == 0) {
		var buttons = $(response).find('buttons').first();
		buttons =  $(buttons).children();
		buttons.each(function() {
			var btn=$(this);
			var name=btn.attr("name");
			var text=btn.attr("text");
			var hint=btn.attr("hint") || '';
			btn.attr('table',table);
			var btn_id = 'button-' + id.substr(1) + '-' + name;
			var btn_html = '<button id="'+btn_id+'" title="'+hint+'">' + text + '</button>';
			$(id).append(btn_html);
			var b=$('#'+btn_id);
            b.button({
                icons: { primary: btn.attr("icon") }
                })
			.click(function() {
				buttonClick(btn);
				b.blur(); // this is to redraw the button
			});
		});
	} else {
		var data = response.text();
		showErrorBox(data);
	}
	//$(id+" > div").remove();
	//$(id).html(h);
	console.log('---');
}

function buttonClick(btn, confirmed) {
	console.log("-- button click -- ")
	console.log(btn);

	var table=btn.attr('table');
	var path=getTablePath(table) || '';
	var name=btn.attr('name');
	var act=btn.attr('act');
	var select=btn.attr('select') || 'one';
	var data=serializeTableForm(table);

	console.log("button table: "+table);
	console.log("button path: "+path);

	if (name=='add' && act=='add') {
		addDialog(path);
		return;
	}

	if ((select=='one' || select=='many') && data.length < 1) {
		Alert.error("You must select at least one item");
		return;
	}

	if (select!='many' && data.length > 1) {
		Alert.error("This action does not support multi select");
		return;
	}

	if (name=='delete' && act=='delete' && confirmed!=true) {
		var items=$.map(data, function(o) {
				return o['value'];
			}).join(', ');
		var m="Are you sure you want to delete ";
		m+=items;
		var func=(function() {buttonClick(btn,true);});
		confirmDialog('Delete confirmation', m, func);
		return;
	}

	if (act=='confirm' && confirmed!=true) {
		var m=btn.attr('confirm');
		var func = ( function() {buttonClick(btn, true);} );
		confirmDialog('Confirmation', m, func);
		return;
	}

	data.push({name: 'path', value: path});
	data.push({name: 'name', value: name});

	if (act == 'js') {
		if (js_buttons[name])
			js_buttons[name].call(btn, data);
		else
			console.log('cannot handle button click');
		console.log('--- js button');
		return;
	}

	$.ajax ({
		url: "/vsa/xml/buttonClick",
		cache: false,
		type: 'POST',
		data: data,
		dataType: 'xml',
		success: function(data) {
			var response=$(data).find('response').first();
			handleButtonClickResult(table, response);
		},
		error: function(xml, text, err) {
			Alert.error('buttonClick error: '+text);
		}
	});
	console.log("---");
}

function handleButtonClickResult(table, response) {
	var rc = response.attr('rc');
	var data = response.text();
	var RC_FORM = 2;

	if (rc == 0) {
		if (data == '')
			data = 'operation successful';
		Alert.info(data);

		if (table.search('manage-table') >= 0)
			refreshTree();
		else
			refreshTable(table);

	} else if (rc == 1) {
		if (data.length < 50)
			Alert.error(data);
		else
			showErrorBox(data);

	} else if (rc == RC_FORM) {
		var title = response.attr('title');
		console.log('handleButtonClickResult: title: '+title);
		showFormDataDialog(title, data, table);
	}
}
