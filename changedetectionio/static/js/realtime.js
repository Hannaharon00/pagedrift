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
            
            return false;
        });


        // Only the actual operation buttons carry name="op"; this excludes UI-only
        // buttons in the bar such as "Invert" (client-side selection toggle).
        $('#checkbox-operations button[name="op"]').on('click.socketHandlerNamespace', function (e) {
            e.preventDefault();
            const $button = $(this);
            const op = $button.val();
            // The cross-page selection store (watch-overview.js) is the source of
            // truth when present — it includes rows selected on other pages, not
            // just the visible checked boxes. Fall back to the DOM if absent.
            const watchSel = window.cdioWatchSelection;
            const checkedUuids = watchSel
                ? watchSel.all()
                : $('input[name="uuids"]:checked').map(function () {
                    return this.value.trim();
                }).get();

            // Check if this button requires confirmation
            console.log('Button clicked, op:', op, 'requires-confirm:', $button.is('[data-requires-confirm]'));
            if ($button.is('[data-requires-confirm]')) {
                console.log('Showing modal confirmation for operation:', op);
                const config = {
                    type: $button.data('confirm-type') || 'danger',
                    title: $button.data('confirm-title') || 'Confirm Action',
                    message: $button.data('confirm-message') || '<p>Are you sure you want to proceed?</p>',
                    confirmText: $button.data('confirm-button') || 'Confirm',
                    cancelText: $button.data('cancel-button') || 'Cancel',
                    onConfirm: function() {
                        console.log(`Socket.IO: Sending watch operation '${op}' for UUIDs:`, checkedUuids);
                        socket.emit('checkbox-operation', {
                            op: op,
                            uuids: checkedUuids,
                            extra_data: $('#op_extradata').val()
                        });
                        // Keep the rows selected after the operation so further
                        // actions can be applied to the same selection — except
                        // delete, where the rows (and their UUIDs) are now gone.
                        if (op === 'delete' && watchSel) {
                            watchSel.clear();
                            if (watchSel.refreshUI) watchSel.refreshUI();
                        }
                    }
                };
                ModalDialog.confirm(config);
            } else {
                console.log(`Socket.IO: Sending watch operation '${op}' for UUIDs:`, checkedUuids);
                socket.emit('checkbox-operation', {
                    op: op,
                    uuids: checkedUuids,
                    extra_data: $('#op_extradata').val()
                });
                // Keep the rows selected after the operation so further actions
                // can be applied to the same selection.
            }

            return false;
        });

    }


    // Cache DOM elements for performance.
    // queue-size-int is a class (not an id) because the count is rendered in
    // BOTH the desktop sidebar and the hamburger drawer — keep them in sync.
    const queueBubble = document.getElementById('queue-bubble');
    const queueSizeNodes = document.querySelectorAll('.queue-size-int');
    // "Checking now" count - rendered in both the desktop sidebar and the hamburger drawer.
    const checkingNowNodes = document.querySelectorAll('.checking-now-int');
    // Only try to connect if authentication isn't required or user is authenticated
    // The 'is_authenticated' variable will be set in the template
    if (typeof is_authenticated !== 'undefined' ? is_authenticated : true) {
        // Try to create the socket connection to the SocketIO server - if it fails, the site will still work normally
        try {
            // Connect to Socket.IO on the same host/port, with path from template
            const socket = io({
                path: socketio_url,  // This will be the path prefix like "/app/socket.io" from the template
                transports: ['websocket', 'polling'],
                reconnectionDelay: 3000,
                reconnectionAttempts: 25
            });

            // Expose the socket so other pages can attach their own listeners
            // (e.g. the queue page reacts to watch_update / queue_size events).
            window.cdioSocket = socket;
            document.dispatchEvent(new CustomEvent('cdio:socket-ready', { detail: { socket: socket } }));

            // Connection status logging
            socket.on('connect', function () {
                $('#realtime-conn-error').hide();
                console.log('Socket.IO connected with path:', socketio_url);
                console.log('Socket transport:', socket.io.engine.transport.name);
                bindSocketHandlerButtonsEvents(socket);
            });

            socket.on('connect_error', function(error) {
                console.error('Socket.IO connection error:', error);
            });

            socket.on('connect_timeout', function() {
                console.error('Socket.IO connection timeout');
            });

            socket.on('error', function(error) {
                console.error('Socket.IO error:', error);
            });

            socket.on('disconnect', function (reason) {
                console.log('Socket.IO disconnected, reason:', reason);
                $('.ajax-op').off('.socketHandlerNamespace');
                $('#realtime-conn-error').show();
            });

            // Tell the server we're leaving cleanly so it can release the connection
            // immediately rather than waiting for a timeout.
            // Note: this only fires for voluntary closes (tab/window close, navigation away).
            // Hard kills, crashes and network drops will still timeout normally on the server.
            window.addEventListener('beforeunload', function () {
                socket.disconnect();
            });

            socket.on('queue_size', function (data) {
                console.log(`${data.event_timestamp} - Queue size update: ${data.q_length}`);
                const formattedCount = parseInt(data.q_length).toLocaleString() || 'None';
                queueSizeNodes.forEach(node => { node.textContent = formattedCount; });
                document.body.classList.toggle('has-queue', parseInt(data.q_length) > 0);

                // Update queue bubble in action sidebar
                //if (queueBubble) {
                if (0) {
                    const count = parseInt(data.q_length) || 0;
                    const oldCount = parseInt(queueBubble.getAttribute('data-count')) || 0;

                    if (count > 0) {
                        // Format number according to browser locale
                        const formatter = new Intl.NumberFormat(navigator.language);
                        queueBubble.textContent = formatter.format(count);
                        queueBubble.setAttribute('data-count', count);
                        queueBubble.classList.add('visible');

                        // Add large-number class for numbers > 999
                        if (count > 999) {
                            queueBubble.classList.add('large-number');
                        } else {
                            queueBubble.classList.remove('large-number');
                        }

                        // Pulse animation if count changed
                        if (count !== oldCount) {
                            queueBubble.classList.remove('pulse');
                            // Force reflow to restart animation
                            void queueBubble.offsetWidth;
                            queueBubble.classList.add('pulse');
                        }
                    } else {
                        // Hide bubble when queue is empty
                        queueBubble.classList.remove('visible', 'pulse', 'large-number');
                        queueBubble.setAttribute('data-count', '0');
                    }
                }
            })

