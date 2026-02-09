/**
 * API Client for DokyDoc Backend
 * Sprint 2 Extended - Multi-Tenancy & RBAC Support
 *
 * Centralized API client with:
 * - Automatic token injection
 * - Tenant context handling
 * - Error handling
 * - Type-safe requests
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface ApiError {
  detail: string;
  status: number;
}

export class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Get authorization header with token
   */
  private getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('accessToken');

    // Check if token is expired
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        const isExpired = payload.exp * 1000 < Date.now();

        if (isExpired) {
          console.error('[API] Token expired - redirecting to login');
          localStorage.clear();
          if (typeof window !== 'undefined') {
            window.location.href = '/login?expired=true';
          }
          return { 'Content-Type': 'application/json' };
        }
      } catch (e) {
        console.error('[API] Invalid token format:', e);
      }
    }

    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  /**
   * Handle API response
   */
  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      // Handle 401 Unauthorized - token expired or invalid
      if (response.status === 401) {
        console.error('[API] 401 Unauthorized - clearing session and redirecting to login');
        localStorage.clear();
        if (typeof window !== 'undefined') {
          window.location.href = '/login?session=expired';
        }
        throw new Error('Session expired. Please login again.');
      }

      const error: ApiError = {
        detail: 'An error occurred',
        status: response.status,
      };

      try {
        const errorData = await response.json();
        error.detail = errorData.detail || errorData.message || 'An error occurred';
      } catch {
        error.detail = `HTTP ${response.status}: ${response.statusText}`;
      }

      throw error;
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  /**
   * GET request
   */
  async get<T>(endpoint: string, params?: Record<string, string | number | boolean>): Promise<T> {
    const url = new URL(`${this.baseUrl}${endpoint}`);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        url.searchParams.append(key, String(value));
      });
    }

    const headers = this.getAuthHeaders();

    // DEBUG: Log token presence for troubleshooting
    console.log('[API] GET', endpoint, {
      hasToken: !!localStorage.getItem('accessToken'),
      hasAuthHeader: !!headers.Authorization,
      url: url.toString()
    });

    const response = await fetch(url.toString(), {
      method: 'GET',
      headers,
    });

    return this.handleResponse<T>(response);
  }

  /**
   * POST request
   */
  async post<T>(endpoint: string, data?: any): Promise<T> {
    const headers = this.getAuthHeaders();

    // DEBUG: Log token presence for troubleshooting
    console.log('[API] POST', endpoint, {
      hasToken: !!localStorage.getItem('accessToken'),
      hasAuthHeader: !!headers.Authorization,
      url: `${this.baseUrl}${endpoint}`
    });

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    });

    return this.handleResponse<T>(response);
  }

  /**
   * PUT request
   */
  async put<T>(endpoint: string, data?: any): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'PUT',
      headers: this.getAuthHeaders(),
      body: JSON.stringify(data),
    });

    return this.handleResponse<T>(response);
  }

  /**
   * DELETE request
   */
  async delete<T>(endpoint: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      method: 'DELETE',
      headers: this.getAuthHeaders(),
    });

    return this.handleResponse<T>(response);
  }

  /**
   * Login with username and password
   */
  async login(username: string, password: string): Promise<{
    access_token: string;
    token_type: string;
    user: User;
    tenant: Tenant;
  }> {
    // Login endpoint uses form data, not JSON
    const response = await fetch('http://localhost:8000/api/login/access-token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username,
        password,
      }),
    });

    return this.handleResponse(response);
  }
}

// Types
export interface User {
  id: number;
  email: string;
  roles: string[];
  tenant_id: number;
  is_active: boolean;
  created_at: string;
}

export interface Tenant {
  id: number;
  name: string;
  subdomain: string;
  status: string;
  tier: string;
  billing_type: string;
  max_users: number;
  max_documents: number;
  monthly_limit_inr?: number;
  balance_inr?: number;
  settings: Record<string, any>;
  created_at: string;
}

export interface Permission {
  name: string;
  description: string;
}

// Singleton instance
export const api = new ApiClient();
