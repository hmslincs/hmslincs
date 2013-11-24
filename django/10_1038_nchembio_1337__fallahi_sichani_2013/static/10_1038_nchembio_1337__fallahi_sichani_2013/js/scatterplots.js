(function ($) {
  (function () {
     var WIDTH = 375,
         HEIGHT = 375;

     var borderwidth = 0;//30;
     var bordercolor = '#999'
     var outerwidth = WIDTH + borderwidth,
         outerheight = HEIGHT + borderwidth
         voodoo = 1;
     $('#main').width(outerwidth +
                      $('#main table tr:first-child td:first-child')
                          .get(0).getBoundingClientRect().width +
                      voodoo);
     // $('html').css('visibility', 'visible');

     // if (borderwidth == 0) {
     //   $('#main td.stage').css('border-top', '1px solid ' + bordercolor);
     // }

     var svg = d3.select('.stage')
               .append('svg')
                 .attr('width', outerwidth)
                 .attr('height', outerheight)
                 .attr('viewBox', viewbox([-borderwidth/2, -borderwidth/2,
                                           outerwidth, outerheight]));

     // ------------------------------------------------------------------------
     var root = svg.append('g')
                 .attr('class', 'root');

     root.append('rect')
           .attr('class', 'canvas')
           .attr('width', WIDTH)
           .attr('height', HEIGHT)
           .style({fill: 'white',
                   stroke: '#999',
                   'stroke-width': borderwidth});

     // recover WIDTH and HEIGHT with
     // parseInt(d3.select('.stage .root > rect').attr('width'))
     // parseInt(d3.select('.stage .root > rect').attr('height'))

  })();

  // just a stub, in case we want to write a more adaptive/real-time
  // determination of the width for the labels;
  function get_label_strip_width (data) {
    return 85;
  }

  function make_track (FACTORS) {

    var $$ = {};

    function populate_list (list, data, max_width, handlers) {

      var n = data.length,
          min_rows = 3,
          hpadding = 10,
          hmargin = 10,
          borderwidth = 1,
          items,
          width,
          sentinel = String.fromCharCode(29),
          column_order = true;

      if (column_order) {
        _populate_list_0(d3.select('#off-stage ul'), data);

        var all_widths = d3.select('#off-stage')
                           .selectAll('li')
                           .filter(function () {
                              return d3.select(this).style('display') !== 'none';
                            })[0]
                           .map(get_width)
                           .sort(d3.descending),
            min_unpadded_colwidth = acceptable_width(all_widths, 1/(min_rows * 2)),
            min_colwidth = min_unpadded_colwidth + (2 * borderwidth) + hpadding,
            max_ncols = column_order ? 1 + ~~((n - 1)/min_rows)
                                     : ~~((n - 1)/(min_rows - 1)),
            ncols = Math.max(1, Math.min(max_ncols,
                                         //~~Math.sqrt(n),
                                         ~~(max_width/(min_colwidth + hmargin)))),
            nrows = Math.max(min_rows, Math.ceil(n/ncols)),
            tmp = Math.ceil(n/nrows);

        if (ncols > tmp) {
           ncols = tmp;
        }

        var colwidth = (~~(max_width/ncols)) - hmargin,
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
          .style('line-height', (parseInt(lis.style('line-height')) - 1) + 'px')
          .style('width', column_order ? (colwidth + 'px') : '');

      function get_width (t) {
        return Math.ceil(t.getBoundingClientRect().width);
      }

      function _populate_list_0 (list, data, handlers) {
        var lis0 = list.selectAll('li'),
            lis = lis0.data(data),
            enter = lis.enter(),
            exit = lis.exit();
        exit.style('display', 'none');
        if (handlers === undefined) {
          handlers = function () {};
        }
        enter.append('li')
             .each(handlers);

        lis.text(function (d) { return d === sentinel ? 'null' : d.text; })
           .style('display', '')
           .style('visibility',
                  function (d) { return d === sentinel ? 'hidden' : 'visible'; });
      }

      function acceptable_width (descending_widths, f) {
        // f represents the maximum acceptable number of entries in
        // descending_widths that are strictly greater than the value
        // returned by this function
        return descending_widths[Math.floor(descending_widths.length * f)];
      }

      function columnate (array, ncols) {
        var nrows = Math.max(min_rows, Math.ceil(array.length/ncols));
        return d3.transpose(chunk(pad_array(array, nrows * ncols), nrows));
      }

      function pad_array (array, n) {
        return array.concat(d3.range(n - array.length)
                              .map(function () { return sentinel; }));
      }

      function chunk (array, chunksize) {
        return d3.range(array.length/chunksize)
                 .map(function (i) {
                    var s = i * chunksize;
                    return array.slice(s, s + chunksize);
                  });
      }
    }


    $$.update_factor = function (handlers) {
      var pivcol = $(':radio[name=factor]:checked').attr('value');


      // var sbmargin = 25;
      var borderwidth = 1;

      $('#track').css({visibility: 'hidden'});

      var ul = d3.select('#track ul');

      // ul.style({display: '',
      //           width: ''});

      // var lis = ul.selectAll('li')
      //             .style('display', 'none');

      var title = ul.select('.title')
                    .text(pivcol)
                    .style('font-weight', 'bold');

      var items = FACTORS[pivcol] //levels(data, factor)
                    .map(function (lvl) {
                       return { text: lvl }//, 'class': get_class(factor, lvl) };
                     });

      // var bbmargin = 20;
      // $('#track-container').css({'padding-left': bbmargin + 'px',
      //                            'padding-right': bbmargin + 'px'});
      // var width = $('#track-container').width() - (2 * bbmargin);

      var width = $('#track-container').width();
      // console.log(width - sbmargin);
      // populate_list(ul, items, width - sbmargin);
      populate_list(ul, items, width - 2 * borderwidth, handlers);
      $('#track').css({visibility: 'visible'});

      $('#track').css({width: $('#track > ul').width() + 2 * borderwidth,
                       visibility: 'visible'});


      //     labels = d3.selectAll('.stage .label'),
      //     exit = labels.data(FACTORS[pivcol])
      //                  .exit();

      // labels.text(String)
      //       .each(function (d, i) {
      //          d3.selectAll('.row-' + i)
      //            .style('display', '');
      //        });

      // exit  .each(function (d, i) {
      //          d3.selectAll('.row-' + i)
      //            .style('display', 'none');
      //        });
    }

    // d3.selectAll('#track-pad,#labels-strip').style({display: 'none'});

    return $$;
  } // function make_track (FACTORS) {

  function make_plot () {
    var $$ = {};

    // draw plot area
    (function () {
       var outerrect = d3.select('.stage .root > rect');
       var WIDTH = parseInt(outerrect.attr('width'));
       var HEIGHT = parseInt(outerrect.attr('height'));

       // var labelwidth = parseInt(d3.select('#labels-strip rect').attr('width'));
       // var sqrt2 = Math.sqrt(2);
       // var w = labelwidth/sqrt2;

       var borderwidth = 0;//4;
       var rw = WIDTH - borderwidth/2;
       // var rh = HEIGHT - borderwidth/2;

       // var available_width = Math.max((rw - w)/2, rw - rh);
       var available_width = rw;
       var voodoo = 0;
       var margin = 0;//10;
       var dx = (rw - available_width) + margin + voodoo;

       var root = d3.select('.stage .root');
       var plot_g = root.append('g')
                          .attr('class', 'plot')
                          .attr('transform',
                                translate([dx, borderwidth/2]));

       var side = rw - dx;
                      
       plot_g.append('rect')
               .attr('class', 'canvas')
               .attr('width', side)
               .attr('height', side)
               .style({fill: 'white',//'beige',
                       stroke: '#00a',
                       'stroke-width': borderwidth});

        var outerbw = parseInt(outerrect.style('stroke-width'));
        var dh = side + borderwidth - HEIGHT;
        if (dh > 0) {
          var svg = d3.select('#main td.stage > svg');
          var vb = svg.attr('viewBox')
                      .split(' ')
                      .map(function (s) { return parseInt(s); });
          var newh = (vb[3] += dh);
          svg.attr({height: newh, viewBox: viewbox(vb)});
          outerrect.attr('height', HEIGHT + dh);
        }
    })();

    // -------------------------------------------------------------------------

    (function () {
       var padding = {top: 5, right: 5, bottom: 30, left: 30},
           plot_g = d3  .select('.stage .plot')
                      .append('g')
                        .attr('class', 'plot-region')
                        .attr('transform', translate(padding.left, padding.top));

       var canvas = d3.select('.stage .plot .canvas'),
           width = parseInt(canvas.attr('width'))
                   - (padding.left + padding.right),
           height = parseInt(canvas.attr('height'))
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


       var edge_coord;

       function coord (v) {
         return isFinite(v) ? v : edge_coord;
       }

       var marker_size = 30;

       var ccle = d3.svg.symbol().type('circle').size(marker_size);

       function hbar (d, i) {
         var r = Math.sqrt(marker_size / 5) * 1.5;
         return 'M' + -r + ',0H' + r;
       }

       function vbar (d, i) {
         var r = Math.sqrt(marker_size / 5) * 1.5;
         return 'M0' + -r + ',V' + r;
       }

       $$.fix_current =
         function () {
           points_g.selectAll('path:not(.fixed)')
                   .classed('fixed', true);
           $('#clear button').prop('disabled', false);
           //current_color.next();
         };

       $$.have_y_level = function () { return $('.y-level').length > 0; }

       $$.view_data =
         function (data) {
           // if (data.length > 0 && !data[0].hasOwnProperty('x')) {
           //   data = data.map(function (d) { return {x: edge_coord, y: d.y}; });
           // }

           var color = $$.have_y_level() ?
                         current_color() :
                         d3.select('.plot .y.axis line').style('stroke');

           points_g.selectAll('path:not(.fixed)')
                   .data(data)
                   .enter()
                 .append('path');

           points_g.selectAll('path:not(.fixed)').each(function (d) {
                  var s = {},
                      a = {transform: translate(x(coord(d.x)), y(coord(d.y)))};
                  if (isFinite(d.x) && isFinite(d.y)) {
                    a.d = ccle(d);
                    a['class'] = 'circle-marker';
                    s.fill = color;
                  }
                  else if (isFinite(d.x)) {
                    a.d = vbar(d);
                    a['class'] = 'vbar';
                    s.stroke = color;
                  }
                  else {
                    a.d = hbar(d);
                    a['class'] = 'hbar';
                    s.stroke = color;
                  }
                  d3.select(this).attr(a)
                                 .style(s);

                });

            return $$;
         };

       $$.domain = function (domain) {
           x.domain(domain).nice();
           y.domain(domain).nice();
           edge_coord = x.domain()[0];

           var xaxis = d3.svg.axis()
               .scale(x)
               .orient('bottom')
               .ticks(3);

           var yaxis = d3.svg.axis()
               .scale(y)
               .orient('left')
               .ticks(3);

           xaxis_g.call(xaxis);
           yaxis_g.call(yaxis);

           return $$;
         };

       $$.clear_all = function () {
           points_g.selectAll('path')
                 .data([])
               .exit()
               .remove();
           current_color.reset();
           return $$;
         };

       $$.clear_not_fixed = function () {
           points_g.selectAll('path:not(.fixed)')
                 .data([])
               .exit()
               .remove();
           return $$;
         };
    })();

    return $$;
  } // function make_plot () {


  // ---------------------------------------------------------------------------

  function app (STACKED) {

    var $$ = {};

    // ---------------------------------------------------------------------------

    function get_values (name) {
      return $.makeArray($(':radio[name="' + name + '"]')
                          .map(function (_, e) {
                             return $(e).attr('value');
                           }));
    }

    var FACTORS = named_array(get_values('factor').map(function (f) {
                    return [f, d3.set(proj(STACKED, f)).values().sort()];
                  })),
        METRICS = get_values('metric'),
        TRACK = make_track(FACTORS),
        PLOT = make_plot(),
        KEYCOL,
        TRAITS,
        DATA;

    $('#track ul').hover(function () { PLOT.clear_not_fixed(); });

    d3.selectAll('.stage .root .cell')
        .each(function (d) {
           var cell = d3.select(this);
           var rect = cell.select('rect');
           var guides = cell.selectAll('.guide');
           var ll = d3.selectAll('#label-' + d.i + ',' + '#label-' + d.j);
           cell
             .on('mouseover', null)
             .on('mouseover', function () {
                d3.event.stopPropagation();
                // if (!rect.classed('fixed')) {
                if (!cell.classed('fixed')) {
                  var clr = current_color();
                  rect.style('fill', clr);
                  guides.style({display: '', stroke: clr});
                }
                ll.classed('highlit', true);
                var pair = [TRAITS[d.i], TRAITS[d.j]];
                PLOT.view_data(xys(pair, DATA, [KEYCOL]));
              })
             .on('mouseout', function (e) {
                // if (!rect.classed('fixed')) {
                if (!cell.classed('fixed')) {
                  rect.style('fill', 'none');
                  guides.style({display: 'none'});
                }
                ll.classed('highlit', false);
              })
             .on('mouseup', function (e) {
                PLOT.fix_current();
                //rect.classed('fixed', true);
                cell.classed('fixed', true);
                $('#clear button').prop('disabled', false);
              })
             ;
         });

    // $('body')
    //   .append($('<div id="off-stage" ' +
    //             'style="position:absolute;left:-999999px"></div>'));

    // d3.select('#off-stage').append('svg')
    //                          .attr('width', 100000)
    //                          .attr('height', 100000)
    //                          .attr('viewBox', viewbox(-50000, -50000,
    //                                                   100000, 100000))
    //                        .append('g')
    //                        .append('text')
    //                          .attr('id', 'get-width');


    // var lwidth = Math.max.apply(null,
    //                             FACTORS.map(function (f) {
    //               return acceptable_width(get_widths(f,
    //                                                  {'class', '.label'},
    //                                                  {'font-weight', 'bold'})
    //                                         .sort(d3.descending), 0.05);
    //              }));

    function view_data (level) {
      var levels = [level];
      var picked = d3.selectAll('.y-level');
      if (picked[0].length === 1) {
        levels.push(picked.datum().text);        
      }
      PLOT.view_data(xys(levels, DATA, [KEYCOL]));
    }

    // #track li:hover:not(.y-level){
    //   color:white;
    //   opacity:0.75;
    //   filter:alpha(opacity=75);
    // }

    function handlers () {
      $(this).hover(function (e) {
          e.stopPropagation();
          var $li = $(this);
          if ($('.y-level').length > 0) {
            $li.css({'background-color': current_color(),
                     color: 'white'});
          }
          else {
            $li.css({outline: '1px solid black'});
          }
          view_data(d3.select(this).datum().text);
        },
        function () {
          var $li = $(this);
          $li.css({'background-color': '', color: ''});
          if ($li.hasClass('y-level')) return;
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
            }
            else {
              clear_text_selection();

              PLOT.fix_current();
              var item = d3.select('#legend')
                               .append('li')
                                 .datum([$ylevel, $li].map(function (jq) {
                                          return d3.select(jq.get(0)).datum().text;
                                        }));

              item.append('span')
                    .attr('class', 'bullet')
                    .style('color', current_color())
                    .text('\u25CF');

              item.append('span')
                    .text(function (d) { return '\u00A0' + d.join(' vs '); });

              // item.insert('span', ':first-child')
              //       .text(function (d) { return d.join(' vs '); });
              //$li.css({'background-color': ''});

              $li.css({'background-color': current_color()});

              current_color.next();
            }
          }
          else {
            $li.addClass('y-level');
            $li.css({'background-color': ''});
            // $li.css({'background-color': current_color()});
            // $('#reset').prop('disabled', false);
            // current_color.next()
          }
          e.stopPropagation();

        })
             .dblclick(function (e) {
          clear_text_selection();
          e.stopPropagation();
        });
    }

    function update_factor (e) {
      if (!e.currentTarget.checked) { return; }
      clear_all();
      TRACK.update_factor(handlers);
      update_data();
    }

    function update_metric (e) {
      if (!e.currentTarget.checked) { return; }
      update_data();
      var dmn = d3.extent(d3.merge(projn(DATA, TRAITS))
                            .map(function (s) { return +s; }));
      PLOT.domain(dmn);
      PLOT.clear_all();
      var points_g = d3.select('.points');
      d3.selectAll('#legend li').each(function (d, i) {
         if (i === 0) { $('#clear button').prop('disabled', false); }
         PLOT.view_data(xys(d, DATA, [KEYCOL]));
         PLOT.fix_current();
         current_color.next();
      })
    }

    function update_data () {
      var pivcol = $(':radio[name=factor]:checked').attr('value'),
          keycol = next_factor(pivcol),
          valcol = $(':radio[name=metric]:checked').attr('value');
      if (keycol === undefined || valcol === undefined) {
        return;
      }
      KEYCOL = keycol;
      //TRAITS = d3.set(proj(STACKED, pivcol)).values().sort();
      TRAITS = FACTORS[pivcol];

      var unstacked = unstack(STACKED,
                              FACTORS.keys.filter(function (q) {
                                return q !== pivcol;
                              }),
                              pivcol, valcol);

      DATA = flatten_nest(d3.nest()
                            .key(get(keycol))
                            .entries(unstacked));
    }

    function clear_all () {
      PLOT.clear_all();
      $('#legend li').remove();
      $('.y-level').removeClass('y-level')
                   .css('outline', 'none');
      $('#clear button').prop('disabled', true);
    }

    function next_factor (factor) {
      return FACTORS.keys[(1 + FACTORS.keys.indexOf(factor)) % FACTORS.length];
    }

    // -------------------------------------------------------------------------

    (function () {
      function check_0th ($button_group) {
        return $button_group.prop('checked', function (i) { return i === 0; });
      }
      check_0th($(':radio[name=factor]')).change(update_factor).trigger('change');
      check_0th($(':radio[name=metric]')).change(update_metric).trigger('change');
      $('#clear button').click(function (e) {
          if (e.which !== 1) { return; }
          clear_all();
      });

      $('html').css('visibility', 'visible');
    })();

    // -------------------------------------------------------------------------

    return $$;
  } // function app (STACKED) {
  

  // ---------------------------------------------------------------------------

  function pairs_to_object(pairs) {
    var ret = {};
    pairs.forEach(function (p) { ret[p[0]] = p[1]; });
    return ret;
  }

  function get_params () {
    return pairs_to_object(
      $.makeArray($('input[type="radio"]:checked')).map(function (e) {
        return [$(e).attr('name'), $(e).attr('value')];
      })
    );
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
    set_key('pairs', function () { return d3.zip(keys, values); })

    return ret;
  }

  function is_numeric (s) {
    return !isNaN(parseFloat(s)) && isFinite(s);
  }

  function assert (bool, info) {
    if (bool) return;
    var msg = 'assertion failed';
    if (arguments.length > 1) {
      msg += ': ' + info;
    }
    throw new Error(msg);
  }

  // stub to make current_color function visible in scope
  function current_color () {}

  // redefine current_color as a closure
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
  })();

  function copy_font (from, to) {
    var props = 'family size size-adjust stretch style variant weight'
                  .split(' ')
                  .map(function (s) { return 'font-' + s; })
                  .concat(['line-height']);
    copy_font = function (from, to) {
      var $from = $(from),
          $to = $(to);

      props.forEach(function (prop) { $to.css(prop, $from.css(prop)); });
    };
    copy_font(from, to);
  }

  function translate (xy) {
    if (arguments.length == 2) {
      xy = Array.prototype.slice.call(arguments, 0);
    }
    return 'translate(' + xy.join(', ') + ')';
  }

  function viewbox (xywh) {
    if (arguments.length == 4) {
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
        else {
          return values;
        }
      }
      else {
        return [values];
      }
    }
    return _f({values: nest});
  }

  function unstack(data, keycols, pivcol, valcol) {
    var nest = d3.nest()
                 .rollup(function (d) {
                    var o = {}, d0 = d[0];
                    keycols.forEach(function (k) { o[k] = d0[k] });
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

  function get (key) {
    return function (d) { return d[key]; }
  }

  function getn (keys) {
    return function (d) { return keys.map(function (k) { return d[k]; }) }
  }

  function proj (aoo, key) {
    return aoo.map(get(key));
  }

  function projn (aoo, keys) {
    return aoo.map(getn(keys));
  }

  function xys (pair, data, keycols) {
    var from = d3.merge([pair, keycols]),
        keys = pair.length === 1 ? ['y'] : ['x', 'y'],
        to = d3.merge([keys, keycols]),
        aoo = toobjs(projn(data, from), to);
    aoo.forEach( function (a) { keys.map(function (k) { a[k] = +a[k]; }) } );
    return aoo;
  }

  function toobjs (aoa, keys) {
    return aoa.map(function (a) {
      var ret = {};
      keys.forEach(function (k, i) { ret[k] = a[i] });
      return ret;
    })
  }

  function acceptable_width (descending_widths, f) {
    // f represents the maximum acceptable number of entries in
    // descending_widths that are strictly greater than the value
    // returned by this function
    return descending_widths[Math.floor(descending_widths.length * f)];
  }

  function get_width (string, attr, style) {
    var g = d3.select('#get-width');
    if (attr !== undefined) { g.attr(attr); }
    if (style !== undefined) { g.style(style); }

    var ret;
    g.text(string)
     .each(function () { ret = this.getBBox().width; });

    if (attr !== undefined) {
      Object.getOwnPropertyNames(attr)
            .forEach(function (a) { g.attr(a, ''); })
    }
    if (style !== undefined) {
      Object.getOwnPropertyNames(style)
            .forEach(function (a) { g.style(a, ''); })
    }
    return ret;
  }

  // function get_widths (strings, attr, style) {
  //   var g = d3.  select('#off-stage > svg')
  //             .append('g');

  //   var ret = [];

  //   g  .selectAll('text')
  //      .data(strings)
  //      .enter()
  //    .append('text')
  //      .text(String)
  //      .attr(attr || {})
  //      .style(style || {})
  //      .each(function () { ret.push(this.getBBox().width); })

  //   g.remove();
  //   return ret;
  // }

  function clear_text_selection () {
    if (window.getSelection) {
      window.getSelection().removeAllRanges();
    }
    else if (document.selection) {
      document.selection.empty();
    }
  }

  function LOG (o) {
    console.log(JSON.stringify(o));
  }

  // ---------------------------------------------------------------------------

  (function () {
    $('body').append($('<div id="off-stage"><div class="list-container">' +
                       '<ul><li>foo</li></ul></div></div>'));
    copy_font('#track', '#off-stage');
  })();

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
  })();

  $('#usage-wrapper .tab').click(function (e) {
    if (e.which !== 1) { return; }
    var $u = $('#usage-wrapper .usage'),
        cc = $u.hasClass('opened') ? ['opened', 'closed'] : ['closed', 'opened'];
    $u.removeClass(cc[0]).addClass(cc[1]);
  });

  $('#usage-wrapper .tab').hover(function (e) {
    d3.select(this).select('.tab.shy svg').style('display', 'none');
  }, function (e) {
    d3.select(this).select('.tab.shy svg').style('display', '');
  });

  // ---------------------------------------------------------------------------

  (function () {
     var STATIC_URL = window.hmslincs.STATIC_URL;
     var INPUT = STATIC_URL + '10_1038_nchembio_1337__fallahi_sichani_2013/data/dose_response_data.tsv';
     //var INPUT = STATIC_URL + '10_1038_nchembio_1337__fallahi_sichani_2013/data/mf_data_0.tsv';

     d3.tsv(INPUT, function (error, data) {
       assert(error === null);
       app(data);
     });
  })();

})(jQuery);

