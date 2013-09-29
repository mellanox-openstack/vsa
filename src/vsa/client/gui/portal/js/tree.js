jQuery(document).ready(function() {
});

//var manage_tree_interval = undefined;

function initTrees() {
	createManageTree();
	//if (!manage_tree_interval)
	//	manage_tree_interval = setInterval('refreshTree()', 1000);
}

function createManageTree() {
	$("#manage_tree").jstree({
		core: { animation: 0 },
		ui: { select_limit: 1, initially_select: ['disks'] },
		"json_data": {
			"ajax": {
				"url" : "/vsa/tree"
			}
		},
		"plugins": [ "themes", "json_data", "ui" ]
	})
	.bind("select_node.jstree", function (e, data) {
		var node = data.rslt.obj;
		var id = node.attr('id');
		nodeClick(id);
	})
	.bind("loaded.jstree", function(e, data) {
	})
	.bind("reselect.jstree", function(e, data) {
		var is_selected = $("#manage_tree").jstree("is_selected");
		if (!is_selected) {
			var par_id = tree_old_select.parent().parent().attr('id');
			var par = $('#'+par_id);
			var check_and_update = true;
			$("#manage_tree").jstree("select_node", par, check_and_update);
		}
	});

	$("#manage_tree").delegate("a", "dblclick", function() {
		$("#manage_tree").jstree("toggle_node", this);
	});
}

var refreshing_tree=false;
var tree_old_select=undefined;
function refreshTree() {
	console.log("-----refreshing tree-----");
	refreshing_tree=true;
	tree_old_select = $("#manage_tree").jstree("get_selected");
	$("#manage_tree").jstree("refresh");
	refreshing_tree=false;
}

function nodeClick(id) {
	if (refreshing_tree) {return;}
	console.log('-- nodeClick -- '+id);
	var table="#manage-table-form";
	path = $('#'+id).data('jstree').path;
	console.log('-- nodeClick path-- '+path);
	loadDataTable(path, table);
	loadToolbarButtons(path, "#manage-toolbar-buttons", table);

	cleanInternalTabs();
	//showing tabs only for objects
	if(path.split('/').length % 2 != 0) {
		loadInternalTabs(id);
	}
}

function getTreeName(id) {
	console.log("-- getIdTreeName -- tree id: "+id);
	var m='li[id="'+id+'"]:first'
	var a=$(m);
	console.log(a)
	var c=a.children("a")
	console.log("----");
	return c.text()
}

function collapseTree(tree) {
        var o = $("#"+tree);
        $(o).jstree("close_all");
}

function expandTree(tree) {
        var o = $("#"+tree);
        o.jstree("open_all");
}
