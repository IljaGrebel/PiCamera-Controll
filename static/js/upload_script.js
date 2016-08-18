/**
 * Created by iljagrebel on 17.08.16.
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