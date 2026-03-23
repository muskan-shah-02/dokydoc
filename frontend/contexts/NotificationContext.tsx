"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";

interface Notification {
  id: number;
  type: string;
  title: string;
  message: string;
  resource_type: string | null;
  resource_id: number | null;
  is_read: boolean;
  created_at: string | null;
  read_at: string | null;
  details: any;
}

interface NotificationContextType {
  notifications: Notification[];
  unreadCount: number;
  isLoading: boolean;
  refresh: () => void;
  markRead: (id: number) => Promise<void>;
  markAllRead: () => Promise<void>;
}

const NotificationContext = createContext<NotificationContextType>({
  notifications: [],
  unreadCount: 0,
  isLoading: false,
  refresh: () => {},
  markRead: async () => {},
  markAllRead: async () => {},
});

export function useNotifications() {
  return useContext(NotificationContext);
}

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const getHeaders = useCallback((): Record<string, string> => {
    const token = localStorage.getItem("accessToken");
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/notifications/unread", {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setUnreadCount(data.unread_count || 0);
      }
    } catch {
      // Silently fail - notifications are non-critical
    }
  }, [getHeaders]);

  const fetchNotifications = useCallback(async () => {
    setIsLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/notifications/?limit=50", {
        headers: getHeaders(),
      });
      if (res.ok) {
        const data = await res.json();
        setNotifications(data);
      }
    } catch {
      // Silently fail
    } finally {
      setIsLoading(false);
    }
  }, [getHeaders]);

  const refresh = useCallback(() => {
    fetchNotifications();
    fetchUnreadCount();
  }, [fetchNotifications, fetchUnreadCount]);

  const markRead = useCallback(async (id: number) => {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/notifications/${id}/read`, {
        method: "PUT",
        headers: getHeaders(),
      });
      if (res.ok) {
        setNotifications((prev) =>
          prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
    } catch {
      // Silently fail
    }
  }, [getHeaders]);

  const markAllRead = useCallback(async () => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/notifications/read-all", {
        method: "PUT",
        headers: getHeaders(),
      });
      if (res.ok) {
        setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
        setUnreadCount(0);
      }
    } catch {
      // Silently fail
    }
  }, [getHeaders]);

  // Poll for unread count every 30 seconds
  useEffect(() => {
    const token = localStorage.getItem("accessToken");
    if (!token) return;

    fetchUnreadCount();
    fetchNotifications();

    const interval = setInterval(fetchUnreadCount, 30000);
    return () => clearInterval(interval);
  }, [fetchUnreadCount, fetchNotifications]);

  return (
    <NotificationContext.Provider
      value={{ notifications, unreadCount, isLoading, refresh, markRead, markAllRead }}
    >
      {children}
    </NotificationContext.Provider>
  );
}
