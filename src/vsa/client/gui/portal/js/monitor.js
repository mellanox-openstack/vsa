// define console.log incase not running in debug mode
// to avoid warnings and errors
if (!window.console) {
       window.console = function() {};
       console.log = function() {};
}

var mon = undefined;

jQuery(document).ready(function() {
       if (window.mon_params) {

               function on_resize() {
                     var w2 = $('#monitor-cols').width();
                     $('#monitor-chart').width( $(window).width() - w2 - 130 );
                     $('#monitor-chart').height( $(window).height() - 50 );
               }

               create_monitor();
               $(window).resize(on_resize);
               on_resize();

               $(window).unload(function() {
                       close_monitor();
               });
       }
});

function new_monitor_window(id, postdata) {
	var ref = window.open('', id,
		'width=650,height=350,menubar=0,toolbar=0,location=0'+
		',directories=0,status=0,scrollbars=0,resizable=1');
	$(ref.document).load(function() {
		var a = $(ref.document).find("#monitor");
		console.log(a);
	});
	$.post('/vsa/monitor', postdata, function(data) {
		ref.document.open();
		ref.document.write(data);
		ref.document.close();
		ref.focus();
	});

	return ref;
}

function new_monitor(data) {
	var btn = this;
	var json = serialized2json(data);
	var id = 'mon_' + randomString(5);

	if (json.path == '/disks' ||
	    json.path == '/targets' ||
	    json.path == '/raids')
	{
		var ref = new_monitor_window(id, data);
		return;
	}

	var p = json.path.split('/');

	if (p[3] == 'ifs') {
		var ref = new_monitor_window(id, data);
		return;
	}

	Alert.error('Cannot create monitor');
	console.log('unknown path for monitor');
}

function create_monitor() {
	console.log(mon_params);
	var name = mon_params.name[0];
	var path = mon_params.path[0];
	var p = path.split('/');
	var selpath = mon_params.selpath;
	var names = [];
	for (var i in selpath)
		names.push( selpath[i].slice(path.length + 1) );
	console.log(names);

	if (path == '/disks') {
		for (var i in names)
			names[i] = 'D' + names[i];
		mon = new StorageMonitor('monitor');
		mon.param = names.join();

	} else if (p[3] == 'ifs') {
		mon = new NetMonitor('monitor');
		mon.param = names.join();

	} else if (path == '/targets') {
                mon = new TargetMonitor('monitor');
                mon.param = names.join();

	} else if (path == '/raids') {
		for (var i in names)
			names[i] = 'r.' + names[i];

		mon = new StorageMonitor('monitor');
		mon.param = names.join();
	}

	if (mon)
		mon.start();
}

function close_monitor() {
	mon.stop();
}


var monitors = {
	mons: [],
	interval: undefined,

	push: function(m) {
		this.mons.push(m);
	},

	start: function() {
		if (this.interval)
			return;
		var _this = this;
		this.interval = setInterval(function(){_this._work();}, 3000);
		this._work();
	},

	_work: function() {
		for (var i in this.mons) {
			var m = this.mons[i];
			m._work();
		}
	}
};


function get_xml(url, data, cb, sync) {
	//cb_success, cb_error, cb_complete) {
	if (!cb.cb_success)
		cb.cb_success = function(r) {}
	if (!cb.cb_error)
		cb.cb_error = function(x,t,e) {}
	if (!cb.cb_complete)
		cb.cb_complete = function(x,t) {}
	if (!data)
		data = {}

	if (!sync)
		var async = true;
	else
		var async = false;

	var _this = this;

	$.ajax ({
		url: url,
		async: async,
		cache: false,
		type: 'POST',
		data: data,
		dataType: 'xml',
		success: function(data) {
			var response = $(data).find('response').first();
			cb.cb_success.call(_this, response);
		},
		error: function(xml, text, err) {
			clearInterval(_this.interval);
			_this.interval = undefined
			Alert.error('Monitor error: '+text);
		},
		complete: function(xml, text) {
		}
	});
}


var BaseMonitor = function() {
	this._plot = undefined;
	this.monitor_data = [];
	this.x = 0;
	this.interval = undefined;
	this.possible_cols = [];
	this._name = undefined; // generated in init
	// override me
	this.title = '';
	this.div_id = undefined;
	this.chart = undefined;
	this._cat = undefined;
	this._target = undefined;
	this.cols = [];
	this.param = '';

	this._init = function() {
		this.chart = this.div_id + '-chart';
		var html = '<div class="mon-cols"></div>';
		html += '<div id="' + this.chart + '" class="mon-chart"></div>';
		o = $('#'+this.div_id);
		o.html(html);
		this.o = o;
		this.o_cols = o.children('.mon-cols');
		if (!this._name)
			this._name = 'mon_' + randomString(5);
	};

	this.stop = function() {
		var postdata = {
			name: this._name,
			cat: this._cat,
			stop: 1
		};
		get_xml.call(this, '/vsa/xml/monitor', postdata, {}, true);
	};

	this.start = function() {

		this._init();

		if (this.interval)
			return;
		var _this = this;
		this.interval = setInterval(function(){_this._work();}, 3000);
		_this._work();
	};

	this._work = function() {
		if (!this._cat)
			return;
		var postdata = {
			name: this._name,
			cat: this._cat,
			param: this.param
		};
		get_xml.call(this, '/vsa/xml/monitor', postdata, { cb_success: this._handleMonitorResult });
	};

	this._handleMonitorResult = function(response) {
		var rc = response.attr('rc');
		if (rc != 0) {
			var data = response.text();
			Alert.error('Monitor error: '+data);
			return;
		}

		var r = this._prepare_data(response, this._target, this.cols);
		mon_data = r[0];
		mon_series = r[1];

		this.update_cols();

		if (mon_data.length == 0)
			return;

		this._apply_plot(mon_data, mon_series);
	};

	this.update_cols = function() {
		var html = '<form><fieldset><legend>Options:</legend>';
		for (var i in this.possible_cols) {
			var v = this.possible_cols[i];
                        var c = jQuery.inArray(v, this.cols) >= 0 ? 'checked' : '';
			html += '<input type="checkbox" ' + c + ' name="' + v +
			'" value="' + v + '" />' + v + '<br />';
		}
		html += '</fieldset></form>';
		this.o_cols.html(html);
		var form = this.o_cols.children('form');
		var _this = this;
		form.find('input:checkbox').change(function(o) {
			var n = $(this).val();
			var c = $(this).attr('checked');
                        var i = jQuery.inArray(n, _this.cols);
			if (i >= 0 && !c)
				_this.cols.splice(i,1);
			else if (i == -1 && c)
				_this.cols.push(n);
		});
	}

	this._prepare_data = function(response, target, cols) {
		var lines = $(response).find('line');
		var mon_series = [];
		var mon_data = [];
		var _this = this;
		var refresh_pcols = true;
		$(lines).each(function() {
			var line = $(this);
			var device = line.attr(target);
			if (device == 'Total')
				return;
			// collect possible cols
			if (refresh_pcols) {
				var atr = line[0].attributes;
				var pcols = [];
				for (var i = 0; i < atr.length; i++)
					if (atr[i].nodeName != _this._target)
						pcols.push(atr[i].nodeName);
				_this.possible_cols = pcols;
				refresh_pcols = false;
			}
			// get wanted cols
			for (var i in cols) {
				var col = cols[i];
				name = device + '-' + col;
				var data = [[0,0]];
				if (_this.monitor_data[name])
					data = _this.monitor_data[name];
				var col_data = parseFloat( line.attr(col) ).toFixed(2);
				data.push([_this.x, col_data]);
				if (data.length > 21)
					data.shift();
				_this.monitor_data[name] = data;
				mon_data.push(data);
				mon_series.push( { label: name } );
			}
		});
		this.x++;
		return [mon_data, mon_series];
	};

	this._apply_plot = function(mon_data, mon_series) {
		var _this = this;
		if (!this._plot || this._plot.series.length != mon_series.length) {
			if (this._plot)
				this._plot.destroy();
			this._plot = $.jqplot(this.chart, mon_data, {
				title: _this.title,
				axesDefaults: { pad: 1 },
				seriesDefaults: { showMarker: false },
				series: mon_series,
				legend: { show: true }
			});
		} else {
			for (var i = 0; i < mon_data.length; i++)
				this._plot.series[i].data = mon_data[i];
			this._plot.replot({resetAxes:true});
		}

	};
}; // end BaseMonitor


var StorageMonitor = function(id) {
	this.title = 'Storage';
	this.div_id = id;
	this._cat = 'storage';
	this._target = 'Device';
	this.cols = ['rIO_sec'];
}; // end StorageMonitor

StorageMonitor.prototype = new BaseMonitor();


var NetMonitor = function(id) {
	this.title = 'Network';
	this.div_id = id;
	this._cat = 'ifc';
	this._target = 'Interface';
	this.cols = ['RxMB_s'];
}; // end NetMonitor

NetMonitor.prototype = new BaseMonitor();

var TargetMonitor = function(id) {
    this.title = 'Network';
    this.div_id = id;
    this._cat = 'target';
    this._target = 'Target_Lun-Initiator';
    this.cols = ['rIO_sec'];
};

TargetMonitor.prototype = new BaseMonitor();
