Alert = {
	_alert_id: 1,

	info: function(text) {
		this.show(text,'info');
	},

	error: function(text) {
		this.show(text,'alert');
	},

	/*
	 * type:  info, alert
	*/
	show: function(text, type) {
		var div_id = 'alert-popups';
		var o = $('#' + div_id);
		console.log(o);
		if (o.length == 0)
			$('body').append('<div id="' + div_id + '" class="ui-widget popup"></div>');
			var o = $('#' + div_id);
			if (o.length == 0)
				return;
		if (type == 'alert') {
			cls = 'ui-state-error';
		} else {
			cls = 'ui-state-highlight';
			type = 'info';
		}
		var aid = div_id + '-alert' + this._alert_id;
		this._alert_id++;
		var icon = '<span class="ui-icon ui-icon-' + type + '" style="float: left; margin-right: .3em;"></span>';
		var msg = '<span class="ui-widget-content" style="margin-right: .3em; border:0;">' + text + '</span>';
		var p = '<div id="' + aid + '" class="ui-corner-all ' + cls + '">' + icon + msg + '</div>';
		o.append(p);
		var _this = this;
		var hide_func = function(){_this.hide(aid);};
		var timeout = text.split(' ').length * 1000;
		if (timeout < 3000)
			timeout = 3000;
		var tim = setTimeout(hide_func,timeout);
		var p = $('#' + aid);
		p.data('timer', tim);
	},

	hide: function(id) {
		var p = $('#' + id);
		p.removeData('timer');
		p.hide('slow', function() {
			p.remove();
		});
	}
};


function randomString(len, charSet) {
	var text = "";
	var possible = charSet || "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

	for( var i = 0; i < len; i++ )
		text += possible.charAt( Math.floor(Math.random() * possible.length) );

	return text;
}

function serialized2json(data) {
	var json = {};
	for (var i in data) {
		if (!json[data[i].name])
			json[data[i].name] = data[i].value;
		else if (typeof(json[data[i].name]) == 'object')
			json[data[i].name].push( data[i].value );
		else
			json[data[i].name] = [ json[data[i].name], data[i].value ];
	}
	return json;
}

function partial(func /*, 0..n args */) {
	var args = Array.prototype.slice.call(arguments).splice(1);
	return function() {
		var allArguments = args.concat(Array.prototype.slice.call(arguments));
		return func.apply(this, allArguments);
	};
}

function printObject(o) {
    var out = '';
    for (var p in o) {
        out += p + ': ' + o[p] + '\n';
    }
    alert(out);
}
