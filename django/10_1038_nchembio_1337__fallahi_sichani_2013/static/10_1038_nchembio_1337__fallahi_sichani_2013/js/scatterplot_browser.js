/*jslint browser:true,
         nomen:true,
         white:true,
         vars:true,
         maxerr:1000,
         maxlen:80
*/

// BLK
// (function () {
// }());

(function ($) {
  "use strict";
  /*global window,document,console,debugger,jQuery,d3,Error,Math */

  function assert (bool, info) {
    if (bool) { return; }
    var msg = 'assertion failed';
    if (arguments.length > 1) {
      msg += ': ' + info;
    }
    throw new Error(msg);
  }

  function is_numeric (s) {
    return !isNaN(parseFloat(s)) && isFinite(s);
  }

  function named_array (pairs) {
    var ret = pairs.map(function (p) { return p[1]; }),
        keys = pairs.map(function (p) { return p[0]; }),
        values = ret.slice(0),
        k2i = {};

    function set_key(k, v) {
      assert(!is_numeric(k) &&
             !ret.hasOwnProperty(k) &&
             ret[k] === undefined,
             'invalid key: ' + k);
      ret[k] = v;
    }

    keys.forEach(function (k, i) {
      set_key(k, ret[i]);
      k2i[k] = i;
    });

    set_key('keys', keys);
    set_key('values', values);
    set_key('index', function (k) { return k2i[k]; });
    set_key('pairs', function () { return d3.zip(keys, values); });

    return ret;
  }

  var current_color;

  (function () {
    var mult = 360,
        start = 2/3,
        step = Math.sqrt(5) - 2;

    var index = 0;
    current_color = function () {
      return d3.hsl(mult * ((start + index * step) % 1), 0.6, 0.6);
    };
    current_color.reset = function () { index = 0; };
    current_color.next = function () { index += 1; };
  }());

  function translate (xy) {
    if (arguments.length === 2) {
      xy = Array.prototype.slice.call(arguments, 0);
    }
    return 'translate(' + xy.join(', ') + ')';
  }

  function viewbox (xywh) {
    if (arguments.length === 4) {
      xywh = Array.prototype.slice.call(arguments, 0);
    }
    return xywh.join(' ');
  }

  function flatten_nest(nest) {
    function _f (nest) {
      var values = nest.values;
      if (values.every) {
        if (values.every(function (v) { return v.hasOwnProperty('values'); })) {
          return Array.prototype.concat.apply([], values.map(_f));
        }
        return values;
      }
      return [values];
    }
    return _f({values: nest});
  }

  function get (key) {
    return function (d) { return d[key]; };
  }

  function unstack(data, keycols, pivcol, valcol) {
    var nest = d3.nest()
                 .rollup(function (d) {
                    var o = {}, d0 = d[0];
                    keycols.forEach(function (k) { o[k] = d0[k]; });
                    if (valcol !== undefined) {
                      d.forEach(function (e) { o[e[pivcol]] = e[valcol]; });
                    }
                    else {
                      d.forEach(function (e) { o[e[pivcol]] = null; });
                    }
                    return o;
                  });
    keycols.forEach(function (k) { nest.key(get(k)); });
    return flatten_nest(nest.entries(data));
  }

  function getn (keys) {
    return function (d) { return keys.map(function (k) { return d[k]; }); };
  }

  function proj (aoo, key) {
    return aoo.map(get(key));
  }

  function projn (aoo, keys) {
    return aoo.map(getn(keys));
  }

  function toobjs (aoa, keys) {
    return aoa.map(function (a) {
      var ret = {};
      keys.forEach(function (k, i) { ret[k] = a[i]; });
      return ret;
    });
  }

  function xys (pair, data, keycols) {
    var from = d3.merge([pair, keycols]),
        keys = pair.length === 1 ? ['y'] : ['x', 'y'],
        to = d3.merge([keys, keycols]),
        aoo = toobjs(projn(data, from), to);
    aoo.forEach( function (a) { keys.map(function (k) { a[k] = +a[k]; }); } );
    return aoo;
  }

  function interpolate(interval, t) {
    return interval[0] * (1 - t) + interval[1] * t;
  }

  function pad_interval(interval, padding) {
    return [interpolate(interval, -padding),
            interpolate(interval, 1 + padding)];
  }

  function clear_text_selection () {
    if (window.getSelection) {
      window.getSelection().removeAllRanges();
    }
    else if (document.selection) {
      document.selection.empty();
    }
  }

  // ---------------------------------------------------------------------------
  // debugging utils

  function logjson (o) {
    console.log(JSON.stringify(o));
  }

  var time = (function () {
    var start,
        ret     = function () { return new Date().valueOf(); };
    ret.started = function () { return start; };
    ret.elapsed = function () { return ret() - start; };
    ret.reset   = function () { start = ret();
                                return start; };
    ret.reset();
    return ret;
  }());

  // ---------------------------------------------------------------------------

  function make_picker () {
    $('#picker-container').css('width', $('#left-panel').width());

    var $$ = {};

    function populate_list (list, data, max_width, handlers) {

      var sentinel = String.fromCharCode(29);

      function _populate_list_0 (list, data, handlers) {
        var lis0 = list.selectAll('li'),
            lis = lis0.data(data),
            enter = lis.enter(),
            exit = lis.exit();
        exit.style('display', 'none');
        if (handlers === undefined) { handlers = function () { return; }; }

        enter.append('li')
             .each(handlers);

        lis.text(function (d) { return d === sentinel ? 'null' : d.text; })
           .style('display', '')
           .style('visibility',
                  function (d) { return d === sentinel ? 'hidden' : ''; });
      }

      var min_rows = 3;

      function chunk (array, chunksize) {
        return d3.range(array.length/chunksize)
                 .map(function (i) {
                    var s = i * chunksize;
                    return array.slice(s, s + chunksize);
                  });
      }

      function pad_array (array, n) {
        return array.concat(d3.range(n - array.length)
                              .map(function () { return sentinel; }));
      }

      function columnate (array, ncols) {
        var nrows = Math.max(min_rows, Math.ceil(array.length/ncols));
        return d3.transpose(chunk(pad_array(array, nrows * ncols), nrows));
      }

      function get_width (t) {
        return Math.ceil(t.getBoundingClientRect().width);
      }

      function acceptable_width (descending_widths, f) {
        // f represents the maximum acceptable number of entries in
        // descending_widths that are strictly greater than the value
        // returned by this function
        return descending_widths[Math.floor(descending_widths.length * f)];
      }

      var n = data.length,
          hpadding = 10,
          hmargin = 10,
          borderwidth = 1,
          width,
          colwidth,
          items,
          column_order = true;

      // function intpart(x) {
      //   /*jslint bitwise:true */
      //   var notx = ~x;
      //   return ~notx;
      // }

      if (column_order) {
        _populate_list_0(d3.select('#off-stage ul'), data);

        var all_widths = d3.select('#off-stage')
                           .selectAll('li')
                           .filter(function () {
                              return d3.select(this)
                                       .style('display') !== 'none';
                            })[0]
                           .map(get_width)
                           .sort(d3.descending),
            min_unpadded_colwidth = acceptable_width(all_widths,
                                                     1 / (min_rows * 2)),
            min_colwidth = min_unpadded_colwidth + (2 * borderwidth) + hpadding,
            max_ncols = column_order ? 1 + ~~((n - 1) / min_rows)
                                     : ~~((n - 1) / (min_rows - 1)),
            ncols = Math.max(1, Math.min(max_ncols,
                                         //~~(Math.sqrt(n)),
                                         ~~(max_width /
                                            (min_colwidth + hmargin)))),
            nrows = Math.max(min_rows, Math.ceil(n/ncols)),
            tmp = Math.ceil(n/nrows);

        if (ncols > tmp) {
           ncols = tmp;
        }

        colwidth = - hmargin + ~~(max_width/ncols);
        width = ncols * (colwidth + hmargin);

        items = d3.merge(columnate(data, ncols));

      }
      else {
        items = data;
        width = max_width;
      }

      _populate_list_0(list, items, handlers);

      list.style('width', width + 'px');
      var lis = list.selectAll('li');
      lis
          .style('border-width', borderwidth + 'px')
          .style('padding', '0 ' + (hpadding/2) + 'px')
          .style('margin', '0 ' + (hmargin/2) + 'px')
          .style('margin-bottom', '1px')
          .style('line-height',
                 (parseInt(lis.style('line-height'), 10) - 1) + 'px')
          .style('width', column_order ? (colwidth + 'px') : '');

    }

    $$.have_y_level = function () { return $('.y-level').length > 0; };

    $$.update_factor = function (factor, levels, handlers) {
      $('#picker').css({visibility: 'hidden'});

      var ul = $('#picker ul');
      ul.find('.title').text(factor);

      var borderwidth = 1;
      var width = $('#picker-container').width();

      populate_list(d3.select(ul.get(0)),
                    levels.map(function (l) { return {text: l}; }),
                    width - 2 * borderwidth, handlers);
      $('#picker').css({width: ul.width() + 2 * borderwidth, visibility: ''});
    };

    return $$;
  } // function make_picker () {



  function make_plot (__width, __height, __label) {
    var $$ = {};

    var $SVG;

    function setup (WIDTH, HEIGHT) {

       var borderwidth = 0;//30;
       var outerwidth = WIDTH + borderwidth,
           outerheight = HEIGHT + borderwidth;

       var svg = d3.select('.stage')
                 .append('svg')
                   .attr('width', outerwidth)
                   .attr('height', outerheight)
                   .attr('viewBox', viewbox([-borderwidth/2, -borderwidth/2,
                                             outerwidth, outerheight]));
       $SVG = svg;

       // ----------------------------------------------------------------------
       var root = svg.append('g')
                   .attr('class', 'root');

       root.append('rect')
             .attr('width', WIDTH)
             .attr('height', HEIGHT)
             .style({fill: 'white',
                     stroke: '#999',
                     'stroke-width': borderwidth});

       // recover WIDTH and HEIGHT with
       // parseInt(d3.select('.stage .root > rect').attr('width'), 10)
       // parseInt(d3.select('.stage .root > rect').attr('height'), 10)

    } // function setup (WIDTH, HEIGHT)

    setup(__width, __height);

    function append_tspan ($parent, spec) {
      $parent.append('tspan')
             .attr(spec.attr)
             .text(spec.text);
    }

    // draw plot area
    (function () {
       var outerrect = $SVG.select('.root > rect');
       var WIDTH = parseInt(outerrect.attr('width'), 10);
       var HEIGHT = parseInt(outerrect.attr('height'), 10);

       var borderwidth = 0;//4;
       var rw = WIDTH - borderwidth/2;

       var available_width = rw;
       var voodoo = 0;
       var margin = 0;//10;
       var dx = (rw - available_width) + margin + voodoo;

       var root = $SVG.select('.root');
       var plot_g = root.append('g')
                          .attr('class', 'plot')
                          .attr('transform',
                                translate([dx, borderwidth/2]));

       var side = rw - dx;
                      
       plot_g.append('rect')
               .attr('class', 'canvas')
               .attr('width', side)
               .attr('height', side)
               .style({'stroke-width': borderwidth});

       //var outerbw = parseInt(outerrect.style('stroke-width'), 10);
       var dh = side + borderwidth - HEIGHT;
       if (dh > 0) {
         var svg = $SVG;
         var vb = svg.attr('viewBox')
                     .split(' ')
                     .map(function (s) { return parseInt(s, 10); });
         vb[3] += dh;
         svg.attr({height: vb[3], viewBox: viewbox(vb)});
         outerrect.attr('height', HEIGHT + dh);
       }
    }());

    // -------------------------------------------------------------------------

    (function () {
       var padding = {top: 5, right: 1, bottom: 25, left: 29},
           plot_g = $SVG.select('.stage .plot')
                      .append('g')
                        .attr('class', 'plot-region')
                        .attr('transform',
                              translate(padding.left, padding.top));

       var canvas = $SVG.select('.plot .canvas'),
           width = parseInt(canvas.attr('width'), 10)
                   - (padding.left + padding.right),
           height = parseInt(canvas.attr('height'), 10)
                   - (padding.top + padding.bottom);

       plot_g.append('rect')
               .attr('class', 'frame')
               .attr('width', width)
               .attr('height', height);

       var x = d3.scale.linear().range([0, width]),
           y = d3.scale.linear().range([height, 0]);

       var xaxis_g = plot_g.append('g')
                             .attr('class', 'x axis')
                             .attr('transform', 'translate(0,' + height + ')');

       var yaxis_g = plot_g.append('g')
                             .attr('class', 'y axis');

       var size = Math.min(width, height);
       plot_g.append('path')
               .attr('class', 'diagonal')
               .attr('d', 'M0,' + size + 'L' + size + ',0');

       var points_g = plot_g.append('g')
                              .attr('class', 'points');

       var PLOT_RANGE_PADDING,
           EDGE_PARAM,
           CIRC,
           HBAR,
           VBAR;

       (function () {
          assert(width === height);
          var side = width,
              margin = 3.5,
              halfwidth = 3.5,
              radius = 5.5,
              abs_padding = 2 * margin + 2 * halfwidth + radius,
              rel_padding = abs_padding/(side - 2 * abs_padding),
              plot_label = plot_g.append('g')
                                   .attr('transform',
                                         translate(abs_padding, 0))
                                 .append('text')
                                 .append('tspan')
                                   .attr('class', 'plot-label')
                                   .attr('dy', '2ex');

          __label.forEach(function (t) { append_tspan(plot_label, t); });

          PLOT_RANGE_PADDING = rel_padding;
          EDGE_PARAM = (margin + halfwidth)/abs_padding;

          CIRC = d3.svg.symbol().type('circle')
                   .size(radius*radius*Math.PI)();

          HBAR = 'M' + -halfwidth + ',0H' + halfwidth;
          VBAR = 'M0' + -halfwidth + ',V' + halfwidth;
       }());

       var xcoord,
           ycoord;

       $$.domain = function (domain) {
           var dmn = pad_interval(domain, PLOT_RANGE_PADDING);
           x.domain(dmn);
           y.domain(dmn);

           var edge_coord = (domain[0] * EDGE_PARAM) +
                            (dmn[0]    * (1 - EDGE_PARAM));

           xcoord = ycoord = function (v) {
             return isFinite(v) ? v : edge_coord;
           };

           var xaxis = d3.svg.axis()
               .scale(x)
               .orient('bottom')
               .ticks(4);

           var yaxis = d3.svg.axis()
               .scale(y)
               .orient('left')
               .ticks(4);

           xaxis_g.call(xaxis);
           yaxis_g.call(yaxis);

           return $$;
         };

       $$.fix_current =
         function () {
           points_g.selectAll('g:not(.fixed)')
                   .classed('fixed', true);
           $('#clear button').prop('disabled', false);
           //$('#clear button').css('visibility', 'visible');
         };

       $$.view_data =
         function (data) {
           var have_y_level = $('.y-level').length > 0,
               color = have_y_level ? current_color()
                                    : $SVG.select('.plot .y.axis line')
                                          .style('stroke');


           points_g.selectAll('g:not(.fixed)')
                   .data(data)
                   .enter()
                 .append('g')
                   .attr('class', 'scatterplot-marker')
                   .each(function () {
                      var $this = d3.select(this);
                      $this.append('path')
                             .attr({'class': 'hbar', d: HBAR});
                      $this.append('path')
                             .attr({'class': 'vbar', d: VBAR});
                      $this.append('path')
                             .attr({'class': 'circ', d: CIRC})
                           .append('svg:title')
                             .text(function (d) { return d.title; });
                    })


           points_g.selectAll('g:not(.fixed)')
                   .attr('transform', function (d) {
                            return translate(d3.round(x(xcoord(d.x)), 1),
                                            d3.round(y(ycoord(d.y)), 1));
                         })
                   .attr({fill: color, stroke: color})
                   .each(function (d) {
                  var $this = d3.select(this);
                  $this.selectAll('path').style('visibility', 'hidden');
                  // if (isFinite(d.y) && isFinite(d.x)) {
                  if (isFinite(d.y) && !(have_y_level && !isFinite(d.x))) {
                    $this.select('.circ').style('visibility', 'visible');
                  }
                  else {
                    if (!isFinite(d.x)) {
                      $this.select('.hbar').style('visibility', 'visible');
                    }
                    // if (have_y_level && !isFinite(d.y)) {
                    if (!isFinite(d.y)) {
                      $this.select('.vbar').style('visibility', 'visible');
                    }
                  }
                });

            return $$;
         };

       $$.clear_all = function () {
           points_g.selectAll('g')
                 .data([])
               .exit()
               .remove();
           current_color.reset();
           return $$;
         };

       $$.clear_not_fixed = function () {
           points_g.selectAll('g:not(.fixed)')
                 .data([])
               .exit()
               .remove();
           return $$;
         };
    }());

    return $$;
  } // function make_plot () {


  // ---------------------------------------------------------------------------

  function app (STACKED_DATA) {

    var $$ = {};

    // -------------------------------------------------------------------------

    function get_values (name) {
      return $.makeArray($(':radio[name="' + name + '"]'))
                        .map(function (e) {
                           return $(e).attr('value');
                         });
    }

    var METRICS;
    (function () {
       var dy = 4;  // NB: this should be 1/3 of .plot-label's font-size

       // NB: subscripting should really be done with
       // baseline-shift="sub" rather than mucking around with dy, but
       // neither FF nor IE support it yet (131201U).

       METRICS =
         named_array(
           [
            // ['log10[EC50 (M)]',
            //  [{attr: {},                              text: 'EC'},
            //   {attr: {'class': 'subscript', dy: +dy}, text: '50'},
            //   {attr: {                      dy: -dy}, text: ' (log'},
            //   {attr: {'class': 'subscript', dy: +dy}, text: '10'},
            //   {attr: {                      dy: -dy}, text: ')'}]],
            ['log10[IC50 (M)]',
             [{attr: {},                              text: 'IC'},
              {attr: {'class': 'subscript', dy: +dy}, text: '50'},
              {attr: {                      dy: -dy}, text: ' (log'},
              {attr: {'class': 'subscript', dy: +dy}, text: '10'},
              {attr: {                      dy: -dy}, text: ')'}]],
            ['log10[GI50 (M)]',
             [{attr: {},                              text: 'GI'},
              {attr: {'class': 'subscript', dy: +dy}, text: '50'},
              {attr: {                      dy: -dy}, text: ' (log'},
              {attr: {'class': 'subscript', dy: +dy}, text: '10'},
              {attr: {                      dy: -dy}, text: ')'}]],
            ['HillSlope',
             [{attr: {},                              text: 'Hill Slope'}]],
            // ['E_inf',
            //  [{attr: {'class': 'math'},               text: 'E'},
            //   {attr: {                      dy: +dy}, text: '\u221E'}]],
              // '\u221E' (aka &infin;) does not get the "subscript"
              // class because it is already tiny;
            ['E_max',
             [{attr: {'class': 'math'},               text: 'E'},
              {attr: {'class': 'subscript', dy: +dy}, text: 'max'}]]//,
            // ['AUC',
            //  [{attr: {},                              text: 'AUC'}]]
           ]
         );
    }());

    var FACTORS = named_array(get_values('factor').map(function (f) {
                    return [f, d3.set(proj(STACKED_DATA, f)).values().sort()];
                  })),
        PICKER = make_picker(FACTORS),
        KEYCOL,
        ncols = 2,
        ww = $('#main .centered-track').width(),
        lpw = $('#left-panel').width(),
        pw = $('#picker-container').width(),
        side = ~~((ww - lpw)/ncols),
        //zide = function () { return ~~((ww - $('#left-panel').width())/ncols); },
        PLOTS = named_array(METRICS.keys.map(function (k) {
          return [k, make_plot(side, side, METRICS[k])];
        }));

    $('#widget').width(ww);

    $('#picker ul').hover(function (e) {
        if (e.shiftKey) { return; } 
        PLOTS.forEach(function (p) { p.clear_not_fixed(); });
    });

    function toxys (levels, data) {
      var ret = xys(levels, data, [KEYCOL]);
      if (KEYCOL !== 'title') {
        ret.forEach(function (d) {
          d.title = d[KEYCOL];
          delete d[KEYCOL];
        });
      }
      return ret;
    }

    function view_data (level) {
      var levels = [level];
      var picked = d3.selectAll('.y-level');
      if (picked[0].length === 1) {
        levels.push(picked.datum().text);
      }
      PLOTS.forEach(function (p) {
        p.view_data(toxys(levels, p.__data));
      });
    }

    function fix_current () {
      PLOTS.forEach(function (p) { p.fix_current(); });
    }

    function handlers () {
      $(this).hover(function (e) {
          e.stopPropagation();
          var $li = $(this);
          if ($('.y-level').length > 0) {
            $li.css({'background-color': current_color(),
                     color: 'white',
                     opacity: 0.75,
                     filter: 'alpha(opacity=75)'});
          }
          else {
            $li.css({outline: '1px solid black'});
          }
          view_data(d3.select(this).datum().text);
        },
        function () {
          var $li = $(this);
          $li.css({'background-color': '',
                   color: '',
                   opacity: 1,
                   filter: 'alpha(opacity=100)'});
          if ($li.hasClass('y-level')) { return; }
          $li.css({outline: 'none'});
        })
             .click(function (e) {
          if (e.which !== 1) { return; }
          var $li = $(this);
          var $ylevel = $('.y-level');
          if ($ylevel.length > 0) {
            if ($li.hasClass('y-level') && !e.shiftKey) {
              $li.removeClass('y-level');
              $li.css({'background-color': '', color: ''});
              $li.trigger('mouseenter');
            }
            else {
              clear_text_selection();

              fix_current();

              var item = d3.select('#legend ul')
                               .append('li')
                                 .datum([$ylevel, $li].map(function (jq) {
                                          return d3.select(jq.get(0))
                                                   .datum()
                                                   .text;
                                        }));

              var mini_table = item.append('table').append('tr');

              mini_table.append('td')                        
                          .attr('class', 'bullet')
                          .style('color', current_color())
                          .text('\u25CF');

              mini_table.append('td')                        
                          .attr('class', 'entry')
                          .text(function (d) { return d.join(' vs '); });

              $(item.node()).height(parseInt(mini_table.style('height'), 10));

              $li.css({color: 'white',
                       'background-color': current_color(),
                       opacity: 1,
                       filter: 'alpha(opacity=100)'});

              current_color.next();
            }
          }
          else {
            $('#clear button').prop('disabled', false);
            $li.addClass('y-level');
            $li.trigger('mouseenter');
          }
          e.stopPropagation();

        })
             .dblclick(function (e) {
          clear_text_selection();
          e.stopPropagation();
        });
    }

    function next_factor (factor) {
      return FACTORS.keys[(1 + FACTORS.keys.indexOf(factor)) % FACTORS.length];
    }

    function _params () {
      var ret = {};
      ret.pivcol = $(':radio[name=factor]:checked').attr('value');
      ret.keycol = next_factor(ret.pivcol);
      return ret;
    }

    function clear_all () {
      PLOTS.forEach(function (p) { p.clear_all(); });

      $('#legend li').remove();
      $('.y-level').removeClass('y-level')
                   .css('outline', 'none');
      $('#clear button').prop('disabled', true);
      //$('#clear button').css('visibility', 'hidden');
    }

    function _extract_data (keycol, pivcol, valcol) {
      var unstacked = unstack(STACKED_DATA,
                              FACTORS.keys.filter(function (q) {
                                return q !== pivcol;
                              }),
                              pivcol, valcol);

      return flatten_nest(d3.nest()
                            .key(get(keycol))
                            .entries(unstacked));
    }

    function update_factor (e) {
      if (!e.currentTarget.checked) { return; }
      var p = _params();
      if (p.keycol === undefined) {
        return;
      }

      clear_all();
      PICKER.update_factor(p.pivcol, FACTORS[p.pivcol], handlers);
      //update_data();

      KEYCOL = p.keycol;
      METRICS.keys.forEach(function (m, i) {
        var data = _extract_data(p.keycol, p.pivcol, m),
            traits = FACTORS[p.pivcol],
            dmn = d3.extent(d3.merge(projn(data, traits))
                              .map(function (s) { return +s; })),
            plot = PLOTS[i];

        plot.__data = data;
        plot.__traits = traits;

        plot.domain(dmn);
        plot.clear_all();
      });
    }

    // -------------------------------------------------------------------------

    (function () {
      function check_0th ($button_group) {
        return $button_group.prop('checked', function (i) { return i === 0; });
      }

      check_0th($(':radio[name=factor]')).change(update_factor)
                                         .trigger('change');

      $('#clear button').click(function (e) {
          if (e.which !== 1) { return; }
          clear_all();
      });

    }());

    // -------------------------------------------------------------------------

    return $$;
  } // function app (STACKED_DATA) {
  

  // ---------------------------------------------------------------------------


  (function () {
    $('.loading').append($('<div id="off-stage"><div class="list-container">' +
                       '<ul><li>foo</li></ul></div></div>'));

    var props = ['family', 'size', 'size-adjust', 'stretch', 'style', 'variant',
                 'weight'].map(function (s) { return 'font-' + s; })
                          .concat(['line-height']),
        $from = $('#picker'),
        $to = $('#off-stage');

    props.forEach(function (p) { $to.css(p, $from.css(p)); });
  }());


  (function () {
    var side = 26,
        stroke_width = 0,//2,
        radius = 4 - (stroke_width/2),
        w = side - stroke_width,
        //color = $('#main .content').css('background-color');
        color = $('#main .pulldown > div').css('background-color');

    d3  .selectAll('#main .tab > div')
      .append('svg')
        .attr({width: side,
               height: side,
               viewBox: viewbox(-side/2, -side/2, side, side)})
      .append('g')
        .attr('class', 'corner-dingbat')
      .append('rect')
        .attr({'class': 'outer',
               x: -w/2, y: -w/2, width: w, height: w,
               rx: radius, ry: radius})
        .style({stroke: color,
                'stroke-width': stroke_width});

    // d3  .select('#main .tab > .close .corner-dingbat')
    //   .append('g')
    //     .attr('transform', 'rotate(45)')
    //     .each(function () {
    //        var $this = d3.select(this),
    //            r = 7;
    //        $this.append('line')
    //               .attr({x1: -r, y1: 0, x2: r, y2: 0});
    //        $this.append('line')
    //               .attr({y1: -r, x1: 0, y2: r, x2: 0});
    //     });

    d3   .select('#main .tab > .close .corner-dingbat')
       .append('g')
         .attr('transform', 'rotate(90)')
         .each(function () {
            var $this = d3.select(this);
            $this.append('circle')
                   .attr({'class': 'inner',
                          cx: 0, cy: 0, r: 9});
            $this.append('text')
                   .attr({'text-anchor': 'middle',
                          dy: '0.75ex'})
                   //.text('\u2329');  // bombs on FF 25 + OS X!
                   .text('<');
         });

    d3   .select('#main .tab > .open .corner-dingbat')
         .each(function () {
            var $this = d3.select(this);
            $this.append('circle')
                   .attr({'class': 'inner',
                          cx: 0, cy: 0, r: 9});
            $this.append('text')
                   .attr({'text-anchor': 'middle',
                          dy: '0.75ex'})
                   .text('?');
         });

  }());

  (function () {

    var $centered_track = $('#main .centered-track'),
        $tab = $centered_track.find('.tab'),
        $pulldown = $centered_track.find('.pulldown'),
        top_open = 0,
        rect = function ($sel) { return $sel.get(0).getBoundingClientRect(); };

    function slide (shut, now) {
      var props, cc;
      if (shut) {
        props = {'margin-top': rect($centered_track).top -
                               rect($pulldown).bottom };
        cc = ['closed', 'open'];
      }
      else {
        props = {'margin-top': top_open };
        cc = ['open', 'closed'];
      }

      $pulldown.animate(props, now ? 0 : 200);
      $centered_track.removeClass(cc[1]).addClass(cc[0]);
    }

    $tab.css('right', 18 + rect($centered_track).right - rect($pulldown).right)
        .click(function () {
           var tf = $centered_track.hasClass('open');
           slide(tf);
           //slide($centered_track.hasClass('open'));
         });

    slide(true, true);
  }());

  // ---------------------------------------------------------------------------

  (function () {
    $('.radio-button-group').each(function () {
      var id = $(this).attr('id'),
          name = id.substr(0, id.lastIndexOf('-')) || id;
      $(this).find(':radio').attr('name', name);
    });

  }());

  // ---------------------------------------------------------------------------

  // hack to prevent horizontal shift when vertical scrollbar appears
  (function () {
    var $body = $('body');
    var sb_div = $('<div>').addClass('sb-measure').get(0);
    $('body').append(sb_div);
    var sb_width = sb_div.offsetWidth - sb_div.clientWidth;
    $(sb_div).remove();
    var $window = $(window);
    var delta = $window.width() - $body.width() + sb_width;
    function on_resize () {
      $body.width($window.width() - delta);
    }
    $window.resize(on_resize).trigger('resize');
  }());

  (function () {
     var STATIC_URL = window.hmslincs.STATIC_URL,
         data_dir = STATIC_URL +
                    '10_1038_nchembio_1337__fallahi_sichani_2013/data/';
     // var data_dir = '';

     var INPUT = data_dir + 'dose_response_data.tsv';
     // var INPUT = data_dir + 'mf_data_0.tsv';

     d3.tsv(INPUT, function (error, data) {
       assert(error === null);
       app(data);

       $('.loading').css('visibility', 'visible')
                    .removeClass('loading');
     });
  }());

}(jQuery));
