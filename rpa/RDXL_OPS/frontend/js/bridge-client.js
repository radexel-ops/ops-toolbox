/**
 * VibeOps Bridge WebSocket Client
 *
 * Handles real-time communication with the backend bridge system.
 */

class BridgeClient {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.connected = false;
        this.messageHandlers = new Map();
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
    }

    /**
     * Connect to WebSocket bridge
     */
    async connect() {
        const token = authManager.getAccessToken();
        if (!token) {
            console.error('No auth token available');
            return false;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const url = `${protocol}//${host}/bridge/ws?token=${encodeURIComponent(token)}`;

        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(url);

                this.ws.onopen = () => {
                    console.log('Bridge connected');
                    this.connected = true;
                    this.reconnectAttempts = 0;
                    this.triggerHandler('connected', {});
                    resolve(true);
                };

                this.ws.onclose = (event) => {
                    console.log('Bridge disconnected:', event.code, event.reason);
                    this.connected = false;
                    this.sessionId = null;
                    this.triggerHandler('disconnected', { code: event.code, reason: event.reason });

                    // Attempt reconnect
                    if (event.code !== 4001) { // Not auth error
                        this.attemptReconnect();
                    }
                };

                this.ws.onerror = (error) => {
                    console.error('Bridge error:', error);
                    this.triggerHandler('error', error);
                    reject(error);
                };

                this.ws.onmessage = (event) => {
                    this.handleMessage(event.data);
                };

            } catch (error) {
                console.error('Bridge connection error:', error);
                reject(error);
            }
        });
    }

    /**
     * Disconnect from WebSocket
     */
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
        this.sessionId = null;
    }

    /**
     * Attempt to reconnect
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            this.triggerHandler('reconnect_failed', {});
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`Attempting reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.connect().catch(() => {
                // Reconnect failed, will try again
            });
        }, delay);
    }

    /**
     * Send command to bridge
     * @param {string} text - Command text
     * @param {string} targetAgent - Target agent (default: 'default')
     * @param {boolean} streaming - Enable streaming response (default: true)
     */
    sendCommand(text, targetAgent = 'default', streaming = true) {
        if (!this.connected || !this.ws) {
            console.error('Bridge not connected');
            return false;
        }

        const message = {
            type: 'command',
            payload: {
                text: text,
                target_agent: targetAgent,
                streaming: streaming
            }
        };

        this.ws.send(JSON.stringify(message));
        return true;
    }

    /**
     * Send command and get streaming response via callback
     * @param {string} text - Command text
     * @param {Object} options - Options
     * @param {function} options.onChunk - Called for each streaming chunk
     * @param {function} options.onComplete - Called when response is complete
     * @param {function} options.onError - Called on error
     */
    sendCommandWithStream(text, options = {}) {
        const { onChunk, onComplete, onError } = options;

        if (!this.connected || !this.ws) {
            if (onError) onError(new Error('Bridge not connected'));
            return false;
        }

        // Temporary handlers for this command
        const streamHandler = (payload) => {
            if (payload.status === 'streaming' && onChunk) {
                onChunk(payload.message || payload.chunk || '');
            }
        };

        const responseHandler = (payload) => {
            // Remove temporary handlers
            this.off('stream', streamHandler);
            this.off('response', responseHandler);

            if (payload.status === 'completed' && onComplete) {
                onComplete(payload.result);
            } else if (payload.status === 'error' && onError) {
                onError(new Error(payload.error || 'Unknown error'));
            }
        };

        // Register temporary handlers
        this.on('stream', streamHandler);
        this.on('response', responseHandler);

        // Send command with streaming enabled
        return this.sendCommand(text, 'default', true);
    }

    /**
     * Send ping
     */
    ping() {
        if (!this.connected || !this.ws) {
            return false;
        }

        const message = {
            type: 'ping',
            payload: { timestamp: new Date().toISOString() }
        };

        this.ws.send(JSON.stringify(message));
        return true;
    }

    /**
     * Handle incoming message
     */
    handleMessage(data) {
        try {
            const message = JSON.parse(data);
            const type = message.type;
            const payload = message.payload;

            // Store session ID
            if (type === 'status' && payload.session_id) {
                this.sessionId = payload.session_id;
            }

            // Trigger handlers
            this.triggerHandler(type, payload);
            this.triggerHandler('message', message);

        } catch (error) {
            console.error('Failed to parse bridge message:', error);
        }
    }

    /**
     * Register message handler
     */
    on(type, handler) {
        if (!this.messageHandlers.has(type)) {
            this.messageHandlers.set(type, []);
        }
        this.messageHandlers.get(type).push(handler);
    }

    /**
     * Remove message handler
     */
    off(type, handler) {
        const handlers = this.messageHandlers.get(type);
        if (handlers) {
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    /**
     * Trigger handlers for message type
     */
    triggerHandler(type, payload) {
        const handlers = this.messageHandlers.get(type);
        if (handlers) {
            handlers.forEach(handler => {
                try {
                    handler(payload);
                } catch (error) {
                    console.error(`Handler error for ${type}:`, error);
                }
            });
        }
    }

    /**
     * Check if connected
     */
    isConnected() {
        return this.connected;
    }

    /**
     * Get session ID
     */
    getSessionId() {
        return this.sessionId;
    }
}

// Global bridge client instance
const bridgeClient = new BridgeClient();
