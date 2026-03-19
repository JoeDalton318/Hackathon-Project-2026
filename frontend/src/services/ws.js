import { getAuthToken } from './auth';
import { apiRootUrl } from './api';

let socket = null;
let reconnectTimer = null;
let subscribers = new Set();
let statusSubscribers = new Set();
let shouldReconnect = false;

function toWebSocketBaseUrl(baseUrl) {
    if (!baseUrl || typeof baseUrl !== 'string') {
        return 'ws://localhost:8000';
    }

    if (baseUrl.startsWith('https://')) {
        return baseUrl.replace('https://', 'wss://');
    }

    if (baseUrl.startsWith('http://')) {
        return baseUrl.replace('http://', 'ws://');
    }

    return baseUrl;
}

function notifyStatus(status) {
    statusSubscribers.forEach((callback) => {
        try {
            callback(status);
        } catch (error) {
            console.warn('[WS] status subscriber error', error);
        }
    });
}

function notifyMessage(message) {
    subscribers.forEach((callback) => {
        try {
            callback(message);
        } catch (error) {
            console.warn('[WS] message subscriber error', error);
        }
    });
}

function scheduleReconnect() {
    if (!shouldReconnect || reconnectTimer) {
        return;
    }

    reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        connectWebSocket();
    }, 3000);
}

export function connectWebSocket() {
    const token = getAuthToken();
    if (!token) {
        notifyStatus('disconnected');
        return null;
    }

    if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
        return socket;
    }

    shouldReconnect = true;
    const wsBaseUrl = toWebSocketBaseUrl(apiRootUrl || process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000');
    const wsUrl = `${wsBaseUrl}/ws?token=${encodeURIComponent(token)}`;

    socket = new WebSocket(wsUrl);
    notifyStatus('connecting');

    socket.onopen = () => {
        notifyStatus('connected');
        socket.send('ping');
    };

    socket.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            notifyMessage(payload);
        } catch {
            notifyMessage({ type: 'raw', payload: event.data, timestamp: Date.now() });
        }
    };

    socket.onerror = () => {
        notifyStatus('error');
    };

    socket.onclose = () => {
        socket = null;
        notifyStatus('disconnected');
        scheduleReconnect();
    };

    return socket;
}

export function disconnectWebSocket() {
    shouldReconnect = false;

    if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    if (socket) {
        socket.close();
        socket = null;
    }

    notifyStatus('disconnected');
}

export function subscribeWebSocket(callback) {
    subscribers.add(callback);
    return () => subscribers.delete(callback);
}

export function subscribeWebSocketStatus(callback) {
    statusSubscribers.add(callback);
    return () => statusSubscribers.delete(callback);
}
