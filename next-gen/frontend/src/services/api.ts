import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api/v1';
console.log('API_BASE_URL:', API_BASE_URL);

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for debugging
api.interceptors.request.use(
  (config) => {
    console.log('API Request:', config.method?.toUpperCase(), config.url);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for debugging
api.interceptors.response.use(
  (response) => {
    console.log('API Response:', response.status, response.config.url);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.status, error.response?.data, error.message);
    return Promise.reject(error);
  }
);

export interface CodeCollection {
  id: number;
  name: string;
  slug: string;
  git_url: string;
  description: string;
  owner: string;
  owner_email: string;
  owner_icon: string;
  git_ref: string;
  last_synced: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CodeBundle {
  id: number;
  name: string;
  slug: string;
  display_name: string;
  description: string;
  doc: string;
  author: string;
  support_tags: string[];
  tasks: string[] | null;
  task_count: number;
  created_at: string;
  codecollection: {
    id: number;
    name: string;
    slug: string;
  } | null;
}

export const apiService = {
  // Health check - tests frontend to backend connectivity
  async getHealth() {
    console.log('API: Testing frontend to backend connectivity...');
    try {
      const response = await api.get('/health');
      console.log('API: Backend health response:', response.data);
      
      // Return frontend-specific health info
      return {
        frontend_status: 'connected',
        backend_status: response.data.status,
        backend_database: response.data.database,
        api_base_url: API_BASE_URL,
        connection_test: 'success',
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      console.error('API: Frontend to backend connection failed:', error);
      return {
        frontend_status: 'disconnected',
        backend_status: 'unreachable',
        backend_database: 'unknown',
        api_base_url: API_BASE_URL,
        connection_test: 'failed',
        error: error instanceof Error ? error.message : String(error),
        timestamp: new Date().toISOString()
      };
    }
  },

  // CodeCollections
  async getCodeCollections(): Promise<CodeCollection[]> {
    console.log('API: Getting collections from', `${API_BASE_URL}/registry/collections`);
    const response = await api.get('/registry/collections');
    console.log('API: Collections response:', response.data);
    return response.data;
  },

  async getCodeCollection(id: number): Promise<CodeCollection> {
    const response = await api.get(`/registry/collections/${id}`);
    return response.data;
  },

  // CodeBundles
  async getCodeBundles(params?: {
    skip?: number;
    limit?: number;
    collection_id?: number;
    search?: string;
    tags?: string;
  }): Promise<CodeBundle[]> {
    console.log('API: Getting codebundles from', `${API_BASE_URL}/codebundles`, 'with params:', params);
    const response = await api.get('/codebundles', { params });
    console.log('API: Codebundles response:', response.data);
    return response.data;
  },

  async getCodeBundle(id: number): Promise<CodeBundle> {
    const response = await api.get(`/codebundles/${id}`);
    return response.data;
  },

  // Admin endpoints
  async getPopulationStatus(token: string) {
    const response = await api.get('/admin/population-status', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerDataPopulation(token: string) {
    const response = await api.post('/admin/populate-data', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async clearAllData(token: string) {
    const response = await api.post('/admin/clear-data', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  // Task management endpoints
  async triggerRegistryPopulation(token: string, collectionSlugs?: string[]) {
    const response = await api.post('/tasks/populate-registry', {
      collection_slugs: collectionSlugs
    }, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerCollectionsSync(token: string, collectionSlugs?: string[]) {
    const response = await api.post('/tasks/sync-collections', {
      collection_slugs: collectionSlugs
    }, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerCodebundlesParsing(token: string) {
    const response = await api.post('/tasks/parse-codebundles', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerCodebundlesEnhancement(token: string) {
    const response = await api.post('/tasks/enhance-codebundles', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerAIInsightsGeneration(token: string) {
    const response = await api.post('/tasks/generate-insights', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getTaskStatus(token: string, taskId: string) {
    const response = await api.get(`/tasks/status/${taskId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getActiveTasks(token: string) {
    const response = await api.get('/tasks/active', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getScheduledTasks(token: string) {
    const response = await api.get('/tasks/scheduled', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getTaskHistory(token: string, limit: number = 100) {
    const response = await api.get(`/tasks/history?limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getTaskMetrics(token: string) {
    const response = await api.get('/tasks/metrics', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getWorkerStats(token: string) {
    const response = await api.get('/tasks/workers', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async cancelTask(token: string, taskId: string) {
    const response = await api.post(`/tasks/cancel/${taskId}`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async retryTask(token: string, taskId: string) {
    const response = await api.post(`/tasks/retry/${taskId}`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },
};

export default api;