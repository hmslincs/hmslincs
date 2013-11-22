(function ($) {

  // ----------------------------------------------------------------------
  var PLOT_RANGE_PADDING = 0.02,
      STATIC_URL = window.hmslincs.STATIC_URL,
      INPUT_FILE = STATIC_URL + '10_1038_nchembio_1337__fallahi_sichani_2013/data/dose_response_data.tsv',
      //INPUT_FILE = STATIC_URL + '10_1038_nchembio_1337__fallahi_sichani_2013/data/mf_data_0.tsv',
      XRANGE = [-10.5, -2],
      MK_FN = mk_sigmoids,
      SHAPE = {width: 125, height: 75},
      PARAMS = 'log10[EC50 (M)]	E_inf	HillSlope'.split('\t'),
      FACTORS = 'cell line	drug'.split('\t');

  d3.tsv(INPUT_FILE, function(error, data) {

    var pgetters = PARAMS.map(get),
        params_set = d3.set(PARAMS),
        get_class = mk_get_class(),
        fgetters = FACTORS.map(get),
        grid = build_grid(d3.max(FACTORS.map(function (f) {
                 return levels(data, f).length;
               })), SHAPE),
        get_xy = mk_get_xy(),
        current_color_index = 0;

    // ----------------------------------------------------------------------

    var paths = grid.select('g')
                    .selectAll('path')
                    .data(data)
                    .enter()
                  .append('svg:path')
                    .each(function (d, i) {
                       var classes = d3.zip(FACTORS, fgetters.map(apply(d)))
                                       .map(function (args) {
                                          return get_class.apply(null, args);
                                        })
                                       .sort()
                                       .join(' ');
                       d3.select(this).classed(classes, true);
                     })
                    .datum(function (d) {
                       var params = pgetters.map(apply(d))
                                            .map(function (d) { return +d; });
                       return   params.every(isFinite)
                              ? get_xy(MK_FN.apply(null, params), XRANGE)
                              : [];
                     });

    var domains = d3.transpose(paths.data()
                                    .map(d3.transpose)
                                    .filter(function (p) {
                                      return p.length > 0;
                                     }))
                    .map(function (a) {
                       return pad_interval(d3.extent(d3.merge(a)),
                                           PLOT_RANGE_PADDING);
                     }),
        svg = grid.select('svg'),
        voodoo = 3,
        text_height = svg.select('text').node().getBBox().height + voodoo,
        ranges = [[0, parseInt(svg.attr('width'))],
                  [parseInt(svg.attr('height')), text_height]],
        line = linedrawer(domains, ranges);
        
    paths.attr('d', function(d){ return line(d) });

    var argmax =  FACTORS
                 .map(function (f) {
                   return [f, levels(data, f)];
                  })
                 .sort(function (a, b) {
                   return b[1].length - a[1].length;
                  })[0],
        maxfactor = argmax[0],
        classes = argmax[1].map(function (lvl) {
                    return get_class(maxfactor, lvl);
                  });

    // ----------------------------------------------------------------------

    $('#dose-response-grid-main')
      .append($('<div id="off-stage"><div class="list-container">' +
                '<ul></ul></div></div>'));
    $('#off-stage').css('font', $('#track').css('font'));

    // ----------------------------------------------------------------------

    // instrument button

    var nfactors = FACTORS.length,
        pick = -1;

    $('#toggle')
      .click(function() {
         var factor = FACTORS[pick = (pick + 1) % nfactors],
             other = FACTORS[(pick + 1) % nfactors];

         set_track(data, other);

         var lvls = levels(data, factor),
             nlevels = lvls.length,
             classes = lvls.map(function (lvl) { return get_class(factor, lvl) });

         grid.selectAll('g')
             .each(function (_, i) {
                var g = this, label = '', cls;
                if (i < nlevels) {
                  label = factor + ': "' + lvls[i] + '"';
                  cls = classes[i];
                  grid.selectAll('.' + cls)
                      .each(function(){
                        this.parentNode.removeChild(this);
                        g.appendChild(this)
                      });
                  unhighlight(cls);
                }
                d3.select(g).select('text').text(label);
              });

         d3.select('#grid')
           .selectAll('svg')
           .each(function () {
             var $this = d3.select(this),
                 c = $this.selectAll('path')[0].length;
             $this.style('display', c === 0 ? 'none' : '');
            });

         $('.current-view').text(factor);
         $('.other-view').text(other);

       }).click();

    $('#reset').css('display', '');
    $("#caption").css('visibility', 'visible');

    $('#reset').click(function () {
      reset();
      $(this).prop('disabled', true);
    });

    (function () {
       var w = $(window),
           sc = $('#sticky-container'),
           at = $('#sticky-anchor-top'),
           ab = $('#sticky-anchor-bottom'),

           a = {position: 'absolute', top: '',  bottom: '0'},
           f = {position: 'fixed',    top: '0', bottom: ''},
           r = {position: 'relative', top: '',  bottom: ''};

       function scroll_handler () {
         var st = w.scrollTop();
         sc.css(st + sc.height() > ab.offset().top ? a :
                st               > at.offset().top ? f : r);
       };

       w.scroll(scroll_handler);
       scroll_handler();
    })();

    $('#loading').fadeOut(800);

    // ----------------------------------------------------------------------

    function set_track (data, factor) {
      // var sbmargin = 25;
      var borderwidth = 1;

      $('#track').css({visibility: 'hidden'});

      reset();

      var ul = d3.select('#track ul');

      // ul.style({display: '',
      //           width: ''});

      // var lis = ul.selectAll('li')
      //             .style('display', 'none');

      var title = ul.select('.title')
                    .text(factor)
                    .style('font-weight', 'bold');

      var items = levels(data, factor)
                    .map(function (lvl) {
                       return { text: lvl, 'class': get_class(factor, lvl) };
                     });

      // var bbmargin = 20;
      // $('#track-container').css({'padding-left': bbmargin + 'px',
      //                            'padding-right': bbmargin + 'px'});
      // var width = $('#track-container').width() - (2 * bbmargin);

      var width = $('#track-container').width();
      // console.log(width - sbmargin);
      // populate_list(ul, items, width - sbmargin);
      populate_list(ul, items, width - 2 * borderwidth);
      $('#track').css({visibility: 'visible'});

      $('#track').css({width: $('#track > ul').width() + 2 * borderwidth,
                       visibility: 'visible'});

      return;
    }

    function highlight (cls) {
      refresh();
      d3.select('#grid :first-child')
        .selectAll('.' + cls)
        .classed('unhighlit', false)
        .style('stroke', color(current_color_index))
        .each(function () {
                this.parentNode.appendChild(this);
              });
    }

    function unhighlight (cls) {
      d3.selectAll("." + cls)
        .classed('unhighlit', true)
        .style('stroke', '');
      refresh();
    }

    function refresh () {
      d3.selectAll('path:not(.unhighlit)')
        .each(function () {
                this.parentNode.appendChild(this);
              });
    }

    function reset () {
      $('#track').find('li')
                 .css({'background-color':''})
                 .removeClass('picked');
      current_color_index = 0;
      d3.selectAll('#grid :first-child path')
        .each(function () {
           d3.select(this).classed('unhighlit', true)
                          .style('stroke', '');
        });
    }

    function populate_list (list, data, max_width, callback) {
      console.log(max_width);
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
      list.selectAll('li')
          .style('border-width', borderwidth + 'px')
          .style('padding', '0 ' + (hpadding/2) + 'px')
          .style('margin', '0 ' + (hmargin/2) + 'px')
          .style('width', column_order ? (colwidth + 'px') : '');

      function handlers () {
            $(this).hover(function () {
                var $li = $(this);
                if ($li.hasClass('picked')) return;
                $li.css({'background-color': color(current_color_index)});
                highlight(d3.select(this).datum()['class']);
              },
              function () {
                var $li = $(this);
                if ($li.hasClass('picked')) return;
                $li.css({'background-color': ''});
                unhighlight(d3.select(this).datum()['class']);
              })
                   .click(function (event) {
                if (event.which !== 1) {
                  return;
                }
                var $li = $(this);
                if (!$li.hasClass('picked')) {
                  $li.css({'background-color': color(current_color_index)});
                  $li.addClass('picked');
                  $('#reset').prop('disabled', false);
                  current_color_index += 1;
                }
                event.stopPropagation();
              })
                   .dblclick(function (event) {
                if (window.getSelection) {
                  window.getSelection().removeAllRanges();
                }
                else if (document.selection) {
                  document.selection.empty();
                }
                event.stopPropagation();
              });
      }

      function get_width (t) {
        return Math.ceil(t.getBoundingClientRect().width);
      }

      function _populate_list_0 (list, data, callback) {
        var lis0 = list.selectAll('li'),
            lis = lis0.data(data),
            enter = lis.enter(),
            exit = lis.exit();
        if (callback === undefined) {
          callback = function () {};
        }
        exit.style('display', 'none');
        enter.append('li')
             .each(callback);

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
  });

  function color (i) {
    var
      mult = 360,
      start = 2/3,
      step = Math.sqrt(5) - 2;
    return d3.hsl(mult * ((start + i * step) % 1), 0.6, 0.6);
  }

  function get (key) {
    return function (d) { return d[key]; }
  }

  function proj (aoo, key) {
    return aoo.map(get(key));
  }

  function levels (data, factor) {
    return d3.set(proj(data, factor)).values();
  }

  function DISABLE__build_grid (nvps, shape) {
    var voodoo = 20,
        hmargin = 40,
        WIDTH = $('html').width() - hmargin,
        BORDER_WIDTH = 4,
        PADDING = 2;

    var row,
        table = d3.select('#grid').insert('table', ':first-child'),
        i = 0,
        available_width = WIDTH - BORDER_WIDTH,
        width_per_cell = shape.width + 2 * PADDING + BORDER_WIDTH,
        ncols = Math.floor(available_width/width_per_cell),
        label,
        box;


    while (i < nvps) {
      if (i % ncols == 0) { row = table.append('tr') }
      label = row.append('td')
         .style({'border-width': BORDER_WIDTH + 'px',
                 padding: PADDING + 'px'})
       .append('svg')
         .attr(shape)
       .append('g')
       .append('text').text('placeholder');
      box = label.node().getBBox();
      label.attr({x: 0, y: box.height});
      i += 1;
    }

    table.style('visibility', 'visible');

    return table;
  }

  function build_grid (nvps, shape) {
    var table = d3.select('#grid').insert('div', ':first-child');
    table
        .selectAll('svg')
        .data(d3.range(nvps))
        .enter()
      .append('svg')
        .attr(shape)
      .append('g')
      .append('text')
        .text('placeholder')
        .attr('x', 0)
        .attr('y', function () {
           return this.getBBox().height;
         });

    table.style('visibility', 'visible');
    return table;
  }

  function apply (d) {
    return function (g) { return g(d); };
  }

  function mk_sigmoids(log10ec50, rcvinf, hc) {
    var pow = Math.pow;
    var Q = pow(10, log10ec50 * hc);
    var P = Q * (1 - rcvinf);
    return function(log10dose) {
      return P/(Q + pow(10, log10dose * hc)) + rcvinf;
    };
  }

  function pad_interval(interval, padding) {
    return [interpolate(interval, -padding),
            interpolate(interval, 1 + padding)];
  }

  function interpolate(interval, t) {
    return interval[0] * (1 - t) + interval[1] * t;
  }

  function linedrawer(srcs, tgts) {
    var xyfns = [0, 1].map(function (i) {
      var s = d3.scale.linear().domain(srcs[i]).range(tgts[i]),
          fmt = d3.format('.1f');
      return function (d) { return fmt(s(d[i])); }
    });
    return d3.svg.line().x(xyfns[0]).y(xyfns[1]);
  }

  function vpadding ($e) {
    var extra_padding = 20;
    return Math.ceil($e.get(0).getBoundingClientRect().height + extra_padding) + 'px';
  }

  function mk_get_class () {
    mk_get_class = undefined;
    var memo = d3.map(),
        sep = String.fromCharCode(29),
        prefix = '_',
        next = -1;
    return function (factor, level) {
      var key = factor + sep + level;
      return   memo.has(key)
             ? memo.get(key)
             : memo.set(key, prefix + (next += 1));
    }
  }

  function mk_get_xy() {
    var NPTS = 100,
        mesh = d3.range(NPTS),
        scale = d3.scale
                  .linear()
                  .domain([0, NPTS - 1]);

    return function (fn, xrange) {
      var xs = mesh.map(scale.range(xrange)),
          ys = xs.map(fn);
      return ys.every(isFinite) ? d3.zip(xs, ys) : [];
    }
  }

})(jQuery);
