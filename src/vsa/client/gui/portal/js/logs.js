function initLogs() {
	loadLogsForm();
}

function loadLogsForm() {
	var where="#tab-logs";
	var loadUrl="/vsa/logs";
	var params='';
	$(where).html('<div class="loading">loading logs form</div>').load(loadUrl, params,
	  function(response, status, xhr) {
		if (status=="error") {
			Alert.error("Can't load logs form");
		} else {
			//
		}
	});
}

function showlog(where) {
	$("#showlog-button").attr('disabled', true);
	//var logtype=$("#logs-form > [name=logtype]").val();
	var data=$("#logs-form").serializeArray();
	
	$.ajax ({
		url: "/vsa/xml/getlog",
		cache: false,
		type: 'POST',
		data: data,
		dataType: 'xml',
		success: function(data) {
			var response = $(data).find('response').first();
			handleLogResult(where, response);
		},
		error: function(xml, text, err) {
			showErrorBox('showLog error: '+text);
		},
		complete: function(xml, text) {
			$("#showlog-button").removeAttr('disabled');
		}
	});
}

function handleLogResult(where, response) {
	var w = $('#'+where);
	var rc = response.attr('rc');
	var data = response.text();
	if (rc == 0)
		w.html(data);
	else
		showErrorBox('log error: '+data);
}
