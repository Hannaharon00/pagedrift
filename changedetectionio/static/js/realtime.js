// Socket.IO client-side integration for changedetection.io

$(document).ready(function () {

    function reapplyTableStripes() {
        $('.watch-table tbody tr').each(function(index) {
            $(this).removeClass('pure-table-odd pure-table-even');
            $(this).addClass(index % 2 === 0 ? 'pure-table-odd' : 'pure-table-even');
        });
    }

    function bindSocketHandlerButtonsEvents(socket) {
        $('.ajax-op').on('click.socketHandlerNamespace', function (e) {
            e.preventDefault();
            const op = $(this).data('op');
            const uuid = $(this).closest('tr').data('watch-uuid');
            
            console.log(`Socket.IO: Sending watch operation '${op}' for UUID ${uuid}`);
            
            // Emit the operation via Socket.IO
            socket.emit('watch_operation', {
                'op': op,
                'uuid': uuid
            });
            
