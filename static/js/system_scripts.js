/**
 * Created by iljagrebel on 30.03.16.
 */
window.onload = function () {
    $.ajax({
        type: "GET",
        url: "/system",
        processData: true,
        cache: false,
        success: function (data) {
            var system = jQuery.parseJSON(data);
            $("input[id='_model']").val(system.model);
            $("input[id='_hostname']").val(system.hostname);
            $("input[id='_firmware']").val(system.firmware);
            $("input[id='_version']").val(system.version);
            $("input[id='_hardware']").val(system.hardware);
            $("input[id='_linux']").val(system.linux);
        }
    });

    $.ajax({
        type: "GET",
        url: "/network",
        processData: true,
        cache: false,
        success: function (data) {
            var network = jQuery.parseJSON(data);
            $("input[id='_ipaddress']").val(network.ip_address);
            $("input[id='_subnet']").val(network.subnet);
            $("input[id='_broadcast']").val(network.broadcast);
            $("input[id='_macaddress']").val(network.mac);
        }
    })
};

setInterval(function () {
    $.ajax({
        type: "GET",
        url: "/system",
        processData: true,
        cache: false,
        success: function (data) {
            var system = jQuery.parseJSON(data);
            $("input[id='_systemUptime']").val(system.systemUptime);
            $("input[id='_uptime']").val(system.uptime);
            $("input[id='_cpu']").val(system.cpu);
            $("input[id='_totalmem']").val(system.totalMemory);
            $("input[id='_avaibmem']").val(system.avaibleMemory);
            $("input[id='_usedmem']").val(system.memoryUsed);
            $("input[id='_freemem']").val(system.memoryFree);
        }
    })
}, 1000);
