// jquery content switcher v0.1
// Written by Roi Dayan
// Feb 2, 2011

/* Example:

<script type="text/javascript">
        $("#radio-new").contentSwitcher({
                'selector' : ':radio'
        });
</script>

*/

(function( $ ){
  var methods = {
  	init : function( options ) {
		// default settings
		var settings = {
			'selector'         : ''
		};
		// merge with options
		if ( options ) {$.extend( settings, options );}
		// init
		return this.each(function() {
			var $this = $(this);
			//data = $this.data('contentSwitcher');
			//console.log($this);
			var rad = $this.find(settings.selector);
			//console.log(rad);
			var conts = [];
			var me = $this;
			rad.each(function() {
				var $this = $(this);
				var val = $this.val();
				var content = $("#content-"+val);
				conts.push(content);
				if (!$this.attr('checked')) {
					content.hide();
				}
				$this.bind('click.contentSwitcher',function() {
					jQuery.each(me.data('contentSwitcher').conts, function() {
						this.hide();
					});
					content.show();
				});
			});
			$this.data('contentSwitcher', {
				conts : conts
			});
		});
	},
  	destroy : function( options ) {
		return this.each(function() {
			var $this = $(this);
			//var data = $this.data('tooltip');
			$(window).unbind('.contentSwithcer');
			//data.tooltip.remove();
			//$this.removeData('tooltip');
		})
	}
  };

  // plugin
  $.fn.contentSwitcher = function( method ) {
	// methods
	if ( methods[method] ) {
		return methods[method].apply( this, Array.prototype.slice.call( arguments, 1 ));
	} else if ( !method || typeof method === 'object' ) {
		return methods.init.apply( this, arguments );
	} else {
		$.error( 'Method ' +  method + ' does not exist on jQuery.contentSwithcer' );
	}
  };
})( jQuery );
