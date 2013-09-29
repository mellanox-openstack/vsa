function initTables() {
    var x;
    $("input[name=checkall]").live("click",function () {
        var toCheck = this.checked;
        x = $(this).parents('table').find('tbody tr');
        // avoiding selection in empty tables
        for (row in x)
            if (isRowEmpty(row))
                return;
        x.find(':checkbox').attr('checked', toCheck);
        x.each(function() {
            if (toCheck)
                $(this).addClass('selected');
            else
                $(this).removeClass('selected');
        });
    });
}

function loadDataTable(path, where, url) {
	var $w = $(where);

	var loadUrl = '/vsa/table?path=' + path;

	if (!path && !url)
		loadUrl = $w.data('loadUrl');
	else if (url)
		loadUrl = url;

	if (!loadUrl) {
		console.log('Error refreshing table ' + where + ': no loadUrl');
		return;
	}

	console.log('Load table ' + where + 'from: ' + loadUrl);

	$w.data('loadUrl', loadUrl);

	$.ajaxSetup ({
		cache: false
	});

	$w.html('<div class="loading">loading table</div>').load(
	  loadUrl,
	  function(response, status, xhr) {
		if (status == 'error') {
			$w.html(errorDiv('Error loading table'));
		} else {
			initDataTable(where + ' table');
			initTableClicks(where + ' table');
		}
	});
}

function initDataTable(id) {
	// check for unsort cols
	var aoColumns = [];
	$(id + ' thead th').each(function() {
		if ($(this).hasClass('no_sort'))
			aoColumns.push({
				bSortable: false
			});
		else
			aoColumns.push(null);
	});
	// init data table
	$(id).dataTable({
                bJQueryUI: true,
		bAutoWidth: false,
		bSortClasses: false,
                sPaginationType: 'full_numbers',
		aoColumns: aoColumns
        });
}

function isRowEmpty(row) {
    return $(row).find('td').first().hasClass('dataTables_empty');
}

function initTableClicks(table_id) {
	var $table = $(table_id);
	console.log(' -- init table clicks -- ' + table_id);
	console.log($table);

	function getRowPath(row) {
		return $('input[type="checkbox"]', row).attr('value');
	}

	function rowSelection($row, event) {
		var $checkbox = $(':checkbox', $row).first();
		var $selectedRows = $('.'+SELECT_CLASS, $table)

		// Deselect row
		if($row.hasClass(SELECT_CLASS) && ($selectedRows.length == 1)) {
			$checkbox.removeAttr('checked');
			$row.removeClass(SELECT_CLASS);
			return;
		}

		// Multiple select when ctrl-key is holded or selecting from checkbox
		if(!event.ctrlKey && event.target.nodeName !== 'INPUT') {
			$('.'+SELECT_CLASS, $table).each(function(i, elem) {
				$(elem).removeClass(SELECT_CLASS);
				$(':checkbox', elem).first().removeAttr('checked');
			});
		} else if($row.hasClass(SELECT_CLASS)) { // ctrl-key is pressed
			$checkbox.removeAttr('checked');
			$row.removeClass(SELECT_CLASS);
			return;
		}
		$checkbox.attr('checked', 'checked');
		$row.addClass(SELECT_CLASS);
	}

	// assign click on edit for the table
	$table.delegate('tbody tr', "dblclick", function() {
		if (isRowEmpty(this))
			return;
		var path = getRowPath(this);
		editDialog(path);
	});

	var MAIN_TABLE = "#manage-table-form table";
	var SELECT_CLASS = 'selected';
	$table.delegate('tbody tr', "click", function(event) {
		if (isRowEmpty(this))
			return;
		var $row = $(this);
		rowSelection($row, event);
		if (table_id != MAIN_TABLE)
			return;
		// main table show internal tabs logic
		cleanInternalTabs();
		if ($row.hasClass(SELECT_CLASS)) {
			res_id = getRowPath($row).replace(/[\/:.]/g, '_').substr(1);
			loadInternalTabs(res_id);
		}
	});
}


function getTablePath(id) {
	return $(id+' span[id^="tablepath"]').html();
}

function setTablePath(where, path) {
	var w=where+' span[id^="tablepath"]';
	$(w).html(path);
}

function serializeTableForm(w) {
	//var tablename=$("#manage-table-form table").attr('id');
	return $(w+" :not([name*=_length]):not([name=checkall])").serializeArray()
}

function refreshTable(table) {
	console.log("Refresh table: "+table);
	loadDataTable('', table, '');
}
