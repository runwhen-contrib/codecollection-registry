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

  // Database-driven task management endpoints
  async triggerSeedDatabase(token: string, yamlPath: string = '/app/codecollections.yaml') {
    const response = await api.post('/tasks/seed-database', null, {
      params: { yaml_file_path: yamlPath },
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerValidateYaml(token: string, yamlPath: string = '/app/codecollections.yaml') {
    const response = await api.post('/tasks/validate-yaml', null, {
      params: { yaml_file_path: yamlPath },
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerSyncCollections(token: string) {
    const response = await api.post('/tasks/sync-collections', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerSyncCollection(token: string, collectionId: number) {
    const response = await api.post(`/tasks/sync-collection/${collectionId}`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerParseCodebundles(token: string) {
    const response = await api.post('/tasks/parse-codebundles', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerParseCollection(token: string, collectionId: number) {
    const response = await api.post(`/tasks/parse-collection/${collectionId}`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerEnhanceCodebundles(token: string) {
    const response = await api.post('/tasks/enhance-codebundles', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerEnhanceCodebundle(token: string, codebundleId: number) {
    const response = await api.post(`/tasks/enhance-codebundle/${codebundleId}`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerGenerateMetrics(token: string) {
    const response = await api.post('/tasks/generate-metrics', {}, {
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

  async getTaskHealth(token: string) {
    const response = await api.get('/tasks/health', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  // Admin CRUD endpoints
  async getCollections(token: string, includeInactive: boolean = false) {
    const response = await api.get('/admin/collections', {
      params: { include_inactive: includeInactive },
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getCollection(token: string, collectionId: number) {
    const response = await api.get(`/admin/collections/${collectionId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async createCollection(token: string, collectionData: any) {
    const response = await api.post('/admin/collections', collectionData, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async updateCollection(token: string, collectionId: number, collectionData: any) {
    const response = await api.put(`/admin/collections/${collectionId}`, collectionData, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async deleteCollection(token: string, collectionId: number, hardDelete: boolean = false) {
    const response = await api.delete(`/admin/collections/${collectionId}`, {
      params: { hard_delete: hardDelete },
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getAdminMetrics(token: string, days: number = 7) {
    const response = await api.get('/admin/metrics', {
      params: { days },
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },
};

export default api;