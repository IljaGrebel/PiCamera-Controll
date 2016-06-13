/**
 * Created by iljagrebel on 01.04.16.
 */
$(function ($) {
    $('button').click(function (e) {
        var frm = $(this).parents('form');
        var script = $(this).parents('form').data("script");
        if (frm.hasClass('post')) {
            $.ajax({
                url: './' + script,
                data: $(frm).serialize(),
                type: 'POST',
                dataType: 'text',
                success: function (response) {
                    console.log(response);
                    $(".response-field").html(response);
                },
                error: function (error) {
                    $(".response-field").html(error);
                }
            });
        }
        else if (frm.hasClass('get')) {
            $.ajax({
                url: './' + script,
                data: $(frm).serialize(),
                type: 'GET',
                dataType: 'text',
                success: function (response) {
                    console.log(response);
                    $(".response-field").html(response);
                },
                error: function (error) {
                    $(".response-field").html(error);
                }
            });
        }
    });
});


setInterval(function () {
    $.ajax({
        type: "GET",
        url: "/status",
        processData: true,
        cache: false,
        success: function (data) {
            var status = jQuery.parseJSON(data);
            if ((status.record) == 'recording') {
                $("button[id='start_record']").addClass('btn-danger');
            } else {
                $("button[id='start_record']").removeClass('btn-danger');
            }
            if ((status.record) == 'stopped') {
                $("button[id='stop_record']").addClass('btn-danger');
            } else {
                $("button[id='stop_record']").removeClass('btn-danger');
            }
        }
    });
}, 1000);