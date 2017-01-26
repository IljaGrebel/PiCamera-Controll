/**
 * Created by iljagrebel on 31.03.16.
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

window.onload = function () {
    $.ajax({
        type: "GET",
        url: "/enc_config",
        processData: true,
        dataType: "text",
        cache: false,
        success: function (data) {
            var enc_config = jQuery.parseJSON(data);
            $("input[id='_width']").val(enc_config.width);
            $("input[id='_heigth']").val(enc_config.heigth);
            $("input[id='_record_file']").val(enc_config.record_file);
            $("input[id='_img_file']").val(enc_config.image_file);
            if ((enc_config.video_format) == '.h264') {
                $("option[id='_video_fmt_1']").prop("selected", true);
            }
            if ((enc_config.video_format) == '.mjpeg') {
                $("option[id='_video_fmt_2']").prop("selected", true)
            }

            if ((enc_config.image_format) == '.jpeg') {
                $("option[id='_image_fmt_1']").prop("selected", true)
            }
            if ((enc_config.image_format) == '.png') {
                $("option[id='_image_fmt_2']").prop("selected", true)
            }
            if ((enc_config.image_format) == '.gif') {
                $("option[id='_image_fmt_3']").prop("selected", true)
            }
            if ((enc_config.image_format) == '.bmp') {
                $("option[id='_image_fmt_4']").prop("selected", true)
            }
            if ((enc_config.image_format) == '.yuv') {
                $("option[id='_image_fmt_5']").prop("selected", true)
            }
            if ((enc_config.image_format) == '.rgb') {
                $("option[id='_image_fmt_6']").prop("selected", true)
            }
            if ((enc_config.image_format) == '.rgba') {
                $("option[id='_image_fmt_7']").prop("selected", true)
            }
            if ((enc_config.image_format) == '.bgr') {
                $("option[id='_image_fmt_8']").prop("selected", true)
            }
            if ((enc_config.image_format) == '.bgra') {
                $("option[id='_image_fmt_9']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'none') {
                $("option[id='_camera_effect_1']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'negative') {
                $("option[id='_camera_effect_2']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'solarize') {
                $("option[id='_camera_effect_3']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'sketch') {
                $("option[id='_camera_effect_4']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'denoise') {
                $("option[id='_camera_effect_5']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'emboss') {
                $("option[id='_camera_effect_6']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'oilpaint') {
                $("option[id='_camera_effect_7']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'hatch') {
                $("option[id='_camera_effect_8']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'gpen') {
                $("option[id='_camera_effect_9']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'pastel') {
                $("option[id='_camera_effect_10']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'watercolor') {
                $("option[id='_camera_effect_11']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'film') {
                $("option[id='_camera_effect_12']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'blur') {
                $("option[id='_camera_effect_13']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'saturation') {
                $("option[id='_camera_effect_14']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'colorswap') {
                $("option[id='_camera_effect_15']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'washedout') {
                $("option[id='_camera_effect_16']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'posterise') {
                $("option[id='_camera_effect_17']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'colorpoint') {
                $("option[id='_camera_effect_18']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'colorbalance') {
                $("option[id='_camera_effect_19']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'cartoon') {
                $("option[id='_camera_effect_20']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'deinterlace1') {
                $("option[id='_camera_effect_21']").prop("selected", true)
            }
            if ((enc_config.camera_effect) == 'deinterlace2') {
                $("option[id='_camera_effect_22']").prop("selected", true)
            }
        }
    });

    $.ajax({
        type: "GET",
        url: "/date",
        processData: true,
        cache: false,
        success: function (data) {
            var date = jQuery.parseJSON(data);
            $("input[id='_day']").val(date.day);
            $("input[id='_year']").val(date.year);
            $("input[id='_hour']").val(date.hour);
            $("input[id='_minute']").val(date.minute);
            $("input[id='_second']").val(date.second);
            if ((date.month) == '1') {
                $("option[id='_Jan']").prop("selected", true)
            }
            if ((date.month) == '2') {
                $("option[id='_Feb']").prop("selected", true)
            }
            if ((date.month) == '3') {
                $("option[id='_Mar']").prop("selected", true)
            }
            if ((date.month) == '4') {
                $("option[id='_Apr']").prop("selected", true)
            }
            if ((date.month) == '5') {
                $("option[id='_May']").prop("selected", true)
            }
            if ((date.month) == '6') {
                $("option[id='_Jun']").prop("selected", true)
            }
            if ((date.month) == '7') {
                $("option[id='_Jul']").prop("selected", true)
            }
            if ((date.month) == '8') {
                $("option[id='_Aug']").prop("selected", true)
            }
            if ((date.month) == '9') {
                $("option[id='_Sept']").prop("selected", true)
            }
            if ((date.month) == '10') {
                $("option[id='_Oct']").prop("selected", true)
            }
            if ((date.month) == '11') {
                $("option[id='_Nov']").prop("selected", true)
            }
            if ((date.month) == '12') {
                $("option[id='_Dec']").prop("selected", true)
            }
        }
    });
};