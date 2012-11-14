jQuery(document).ready(function ($) {

    var slider_images = [
        'pakt,igf-1,100,10__perk,fgf-1,100,10.png',
        'pakt,igf-1,100,30__perk,fgf-1,100,30.png',
        'pakt,igf-1,100,90__perk,fgf-1,100,90.png'
    ];
    var timepoints = [10, 30, 90];

    $("#slider").slider({
        value: 0,
        min: 0,
        max: 2,
        slide: function(event, ui) {
            slide_to(ui.value);
        }
    });
    slide_to($("#slider").slider("value"));

    function slide_to(value) {
        var $img = $("#slider-img");
        var src = $img.attr('src');
        var new_src = src.substr(0, src.lastIndexOf('/') + 1) + slider_images[value];
        $img.attr('src', new_src);
        $("#timepoint").val(timepoints[value] + " min");
    }

});
