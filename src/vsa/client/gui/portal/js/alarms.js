function initAlarms() {
	loadAlarms();
}

function loadAlarms() {
	var loadUrl="/vsa/alarms";
	var table="#alarms-table-form";
	loadDataTable('', table, loadUrl);
	loadToolbarButtons("alarms", "#alarms-toolbar-buttons", table);
}
