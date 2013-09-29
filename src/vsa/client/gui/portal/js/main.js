// define console.log incase not running in debug mode
// to avoid warnings and errors
if (!window.console) {
	window.console = function() {};
	console.log = function() {};
}

var js_buttons = {}

jQuery(document).ready(function() {
    $.ajaxSetup ({
            cache: false
    });

    initTabs();
    initDialogs();
    initTrees();
    initToolbars();
    initTables();
    initLogs();
    initAlarms();
    initReports();

    $("#side-bar").resizable({
            handles: 'e',
            resize: function(event,ui) {
                    $(".pagebody").css('margin-left', ui.element.width()+10);
            }
    });

    $("#main-tabs").removeClass("hide");

    // register monitor toolbar button
    js_buttons.extmon = function(data){new_monitor(data);};

    _fix_height = function() {
        $("#tab-manage").height( $("body").height() - $("#tab-manage").offset().top - 30 );
        $("#manage_tree").height( $("body").height() - $("#manage_tree").offset().top - 20 );
    }
    _fix_height();
    $(window).resize(_fix_height);
});

function loadInternalTabs(node_id) {
    var $container = $('#internal-tabs');

    $container.show();

    var $parent_ = $('li[id="'+node_id+'"]').first();
    var $childes = $parent_.children('ul').children('li');
    if ($childes.length == 0)
        return;

    var child_name = $('a', $parent_).first().text();
    var $title = $('<div></div>')
        .text(child_name)
        .addClass('internal-tabs-header');
    var $ul = $('<ul></ul>');
    var $toolbar = $('<div></div>').attr('id', "internal-tabs-toolbar");

    var $tabs = $("<div></div>")
        .addClass('tabs')
        .append($ul);

    $container
        .append($title)
        .append($tabs)
        .append($toolbar);

    $childes.each(function(i, c) {
        var path = $('#'+c.id).data('jstree').path;
        var icon = $('a ins', c).css('background-image');
        var name = path.split('/').pop();
        var tab_name = $(c).children('a').first().text();

        var $form = $('<form></form>').attr('id', 'tab-'+name+'-form');
        var $tab = $('<div></div>')
            .attr('id', 'tab-'+name)
            .append($form);
        $container.append($tab);

        // tab anchor
        var $a = $('<a></a>')
            .attr('href', '#tab-'+name)
            .text(tab_name)
            // When tab is chosen, load the corresponding toolbar
            .click(function() {
                loadToolbarButtons(path, "#internal-tabs-toolbar", '#'+$form.attr('id'));
            });

	var ins = $('<ins></ins>')
            .addClass('tab-icon internal-tab-icon')
            .css('background-image', icon);
        $a.prepend(ins);

        // show toolbars buttons for the first visible tab
        if (i == 0)
            $a.trigger('click');

        $ul.append($('<li></li>').append($a));

        // loading the table for this tab
        loadDataTable(path, '#'+$form.attr('id'), '');
    });

    $container.tabs({
        select: function(e, ui) {
        }
    })
    .tabs("option", "selected", 1)
    .tabs("option", "selected", 0);
}

function cleanInternalTabs() {
    $('#internal-tabs')
    .hide()
    .tabs('destroy')
    .empty();
}

function initTabs() {
	//$("#radioNav").buttonset();

	var $tabs=$("#main-tabs");

        $tabs.tabs({
                select: function(e, ui) {
		},
		ajaxOptions: {
			error: function(xhr, status, index, anchor) {
				$(anchor.hash).html("Couldn't load this tab");
			}
		}
        });

        // workaround to trigger the select event
        $tabs.tabs("option", "selected", 1);
        $tabs.tabs("option", "selected", 0);
}

function errorDiv(m) {
	var h='<div class="ui-state-error ui-corner-all" style="padding: 0pt 0.7em;">'+
	'<p><span class="ui-icon ui-icon-alert" style="float: left; margin-right: 0.3em;"></span>'+
	'<strong>Alert:</strong> '+m+'</p></div></div>';
	return h
}
