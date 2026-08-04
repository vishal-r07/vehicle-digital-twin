/**
 * useWebSocket.js - Custom hook for WebSocket connection management
 * 
 * Features:
 * - Auto-reconnect with exponential backoff
 * - Connection state tracking
 * - Message parsing
 * - Cleanup on unmount
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { WS_URL, RECONNECT_INTERVAL, MAX_RECONNECT_ATTEMPTS } from '../config/constants';

export function useWebSocket(url = WS_URL) {
  const [data, setData] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectCount = useRef(0);
  const reconnectTimer = useRef(null);
  const isMounted = useRef(true);

  const connect = useCallback(() => {
    if (!isMounted.current) return;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMounted.current) return;
        setIsConnected(true);
        setError(null);
        reconnectCount.current = 0;
        console.log('[WS] Connected to', url);
      };

      ws.onmessage = (event) => {
        if (!isMounted.current) return;
        try {
          const parsed = JSON.parse(event.data);
          // Skip connection acknowledgment messages
          if (parsed.type === 'connection') return;
          setData(parsed);
        } catch (e) {
          console.warn('[WS] Parse error:', e);
        }
      };

      ws.onclose = (event) => {
        if (!isMounted.current) return;
        setIsConnected(false);
        
        if (reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            RECONNECT_INTERVAL * Math.pow(1.5, reconnectCount.current),
            30000
          );
          reconnectCount.current += 1;
          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectCount.current})`);
          reconnectTimer.current = setTimeout(connect, delay);
        }
      };

      ws.onerror = (err) => {
        if (!isMounted.current) return;
        setError('WebSocket connection error');
        console.error('[WS] Error:', err);
      };

    } catch (e) {
      setError(e.message);
    }
  }, [url]);

  useEffect(() => {
    isMounted.current = true;
    connect();

    return () => {
      isMounted.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { data, isConnected, error };
}