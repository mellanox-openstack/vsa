function initReports() {
	loadReportsForm();
}

function loadReportsForm() {
	var where="#tab-reports";
	var loadUrl="/vsa/reports";
	var params='';
	$(where).html('<div class="loading">loading reports form</div>').load(loadUrl, params,
	  function(response, status, xhr) {
		if (status=="error") {
			Alert.error("Can't load reports form");
		} else {
			initReportsAutocomplete("#input-report", "#combobox-reports");
		}
	});
}

function initReportsAutocomplete(where, opts) {
	var data=[];
	$(opts+' > option').map(function() {
		var text=$(this).val();
		data.push(text);
	  });
	$(where).autocomplete({
		source: data,
		minLength: 0
	}).focus(function() {
		$(where).autocomplete("search");
	});
}

function showreport(where) {
	$("#showreport-button").attr('disabled', true);
	var data=$("#reports-form").serializeArray();
	
	$.ajax ({
		url: "/vsa/xml/getreport",
		cache: false,
		type: 'POST',
		data: data,
		dataType: 'xml',
		success: function(data) {
			var response=$(data).find('response').first();
			handleReportResult(where, response);
		},
		error: function(xml, text, err) {
			showErrorBox('showReport error: '+text);
		},
		complete: function(xml, text) {
			$("#showreport-button").removeAttr('disabled');
		}
	});
}

function handleReportResult(where, response) {
	var w = $('#'+where);
	var rc = response.attr('rc');
	var data = response.text();
	if (rc == 0)
		w.html(data);
	else
		showErrorBox('report error: '+data);
}
