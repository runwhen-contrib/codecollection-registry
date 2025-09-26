import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api/v1';
console.log('API_BASE_URL:', API_BASE_URL);

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper function to get auth token
const getAuthToken = (): string | null => {
  return localStorage.getItem('auth_token');
};

// Add request interceptor for debugging and auth
api.interceptors.request.use(
  (config) => {
    console.log('API Request:', config.method?.toUpperCase(), config.url);
    
    // Add auth token for admin and tasks endpoints
    if (config.url?.includes('/admin') || config.url?.includes('/tasks')) {
      const token = getAuthToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    
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
  statistics?: {
    codebundle_count: number;
    total_tasks: number;
  };
  versions?: CodeCollectionVersion[];
}

export interface VersionCodebundle {
  id: number;
  name: string;
  slug: string;
  display_name: string | null;
  description: string | null;
  author: string | null;
  support_tags: string[];
  categories: string[];
  task_count: number;
  sli_count: number;
  runbook_path: string | null;
  runbook_source_url: string | null;
  added_in_version: boolean;
  modified_in_version: boolean;
  removed_in_version: boolean;
  discovery_info: any;
}

export interface CodeCollectionVersion {
  id: number;
  version_name: string;
  git_ref: string;
  display_name: string | null;
  description: string | null;
  version_type: string;
  is_latest: boolean;
  is_prerelease: boolean;
  version_date: string | null;
  synced_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  codebundle_count: number;
  codebundles?: VersionCodebundle[];
  codecollection?: {
    id: number;
    name: string;
    slug: string;
    description: string;
    repository_url: string;
  };
}

export interface DiscoveryInfo {
  is_discoverable: boolean;
  platform: string | null;
  resource_types: string[];
  match_patterns: any[];
  templates: string[];
  output_items: any[];
  level_of_detail: string | null;
  runwhen_directory_path: string | null;
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
  slis: string[] | null;
  task_count: number;
  sli_count: number;
  runbook_source_url: string;
  created_at: string;
  discovery: DiscoveryInfo;
  // AI Enhancement fields
  ai_enhanced_description?: string;
  access_level?: 'read-only' | 'read-write' | 'unknown';
  minimum_iam_requirements?: string[];
  enhancement_status?: 'pending' | 'processing' | 'completed' | 'failed';
  last_enhanced?: string;
  ai_enhanced_metadata?: {
    enhanced_tasks?: Array<{
      name: string;
      description: string;
      documentation: string;
      tags: string[];
      steps: string[];
      ai_purpose?: string;
      ai_function?: string;
      ai_requirements?: string[];
    }>;
    model_used?: string;
    enhanced_at?: string;
    service_provider?: string;
    [key: string]: any;
  };
  codecollection: {
    id: number;
    name: string;
    slug: string;
    git_url: string;
    git_ref?: string;
  } | null;
}

export interface Task {
  id: string;
  name: string;
  type: 'TaskSet' | 'SLI' | 'CodeBundle';
  codebundle_id: number;
  codebundle_name: string;
  codebundle_slug: string;
  collection_name: string;
  collection_slug: string;
  description: string;
  support_tags: string[];
  categories: string[];
  author: string;
  runbook_path: string;
  runbook_source_url: string;
  git_url: string;
  git_ref?: string;
}

export interface TasksResponse {
  tasks: Task[];
  total_count: number;
  codebundles_count: number;
  support_tags: string[];
  pagination: {
    limit: number;
    offset: number;
    has_more: boolean;
  };
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

  async getCodeCollectionBySlug(slug: string): Promise<CodeCollection> {
    console.log('API: Getting collection by slug', `${API_BASE_URL}/registry/collections/${slug}`);
    const response = await api.get(`/registry/collections/${slug}`);
    console.log('API: Collection response:', response.data);
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

  async getCodeBundleBySlug(collectionSlug: string, codebundleSlug: string): Promise<CodeBundle> {
    console.log('API: Getting codebundle by slug', `${API_BASE_URL}/collections/${collectionSlug}/codebundles/${codebundleSlug}`);
    const response = await api.get(`/collections/${collectionSlug}/codebundles/${codebundleSlug}`);
    console.log('API: Codebundle response:', response.data);
    return response.data;
  },

  // Tasks
  async getAllTasks(params?: {
    support_tags?: string[];
    search?: string;
    collection_slug?: string;
    limit?: number;
    offset?: number;
  }): Promise<TasksResponse> {
    console.log('API: Getting all tasks from', `${API_BASE_URL}/registry/tasks`, 'with params:', params);
    const searchParams = new URLSearchParams();
    if (params?.support_tags && params.support_tags.length > 0) {
      searchParams.append('support_tags', params.support_tags.join(','));
    }
    if (params?.search) searchParams.append('search', params.search);
    if (params?.collection_slug) searchParams.append('collection_slug', params.collection_slug);
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.offset) searchParams.append('offset', params.offset.toString());
    
    const queryString = searchParams.toString();
    const response = await api.get(`/registry/tasks${queryString ? `?${queryString}` : ''}`);
    console.log('API: Tasks response:', response.data);
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

  // Old getTaskStatus method removed - now using task management endpoint

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

  // AI Configuration endpoints
  async getAIConfigurations(token: string) {
    const response = await api.get('/admin/ai/config', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getActiveAIConfiguration(token: string) {
    const response = await api.get('/admin/ai/config/active', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async createAIConfiguration(token: string, configData: any) {
    const response = await api.post('/admin/ai/config', configData, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async updateAIConfiguration(token: string, configId: number, configData: any) {
    const response = await api.put(`/admin/ai/config/${configId}`, configData, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async deleteAIConfiguration(token: string, configId: number) {
    const response = await api.delete(`/admin/ai/config/${configId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerAIEnhancement(token: string, enhancementRequest: any) {
    const response = await api.post('/admin/ai/enhance', enhancementRequest, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getEnhancementStatus(token: string, taskId: string) {
    const response = await api.get(`/admin/ai/enhance/status/${taskId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getAIStats(token: string) {
    const response = await api.get('/admin/ai/stats', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async resetAIEnhancements(token: string) {
    const response = await api.post('/admin/ai/reset', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  // Admin Inventory endpoints
  async getInventoryStats(token: string) {
    const response = await api.get('/admin/inventory/stats', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getInventoryCodebundles(token: string, params: any = {}) {
    const response = await api.get('/admin/inventory/codebundles', {
      headers: { Authorization: `Bearer ${token}` },
      params
    });
    return response.data;
  },

  async getInventoryCollections(token: string, params: any = {}) {
    const response = await api.get('/admin/inventory/collections', {
      headers: { Authorization: `Bearer ${token}` },
      params
    });
    return response.data;
  },

  async getInventoryCodebundle(token: string, codebundleId: number) {
    const response = await api.get(`/admin/inventory/codebundles/${codebundleId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  // Version management endpoints
  async triggerSyncAllVersions(token: string) {
    const response = await api.post('/admin/sync-all-versions', {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async triggerSyncCollectionVersions(token: string, collectionId: number) {
    const response = await api.post(`/admin/sync-collection-versions/${collectionId}`, {}, {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  async getVersionsStatus(token: string) {
    const response = await api.get('/admin/versions-status', {
      headers: { Authorization: `Bearer ${token}` }
    });
    return response.data;
  },

  // Version endpoints
  async getCollectionVersions(
    collectionSlug: string, 
    includeInactive: boolean = false
  ): Promise<CodeCollectionVersion[]> {
    console.log('API: Getting versions for collection', collectionSlug);
    const params = new URLSearchParams();
    if (includeInactive) params.append('include_inactive', 'true');
    
    const response = await api.get(`/registry/collections/${collectionSlug}/versions?${params.toString()}`);
    console.log('API: Versions response:', response.data);
    return response.data;
  },

  async getVersionByName(
    collectionSlug: string, 
    versionName: string
  ): Promise<CodeCollectionVersion> {
    console.log('API: Getting version by name', collectionSlug, versionName);
    
    const response = await api.get(`/registry/collections/${collectionSlug}/versions/${versionName}`);
    console.log('API: Version response:', response.data);
    return response.data;
  },

  async getLatestVersion(
    collectionSlug: string, 
    versionType?: string
  ): Promise<CodeCollectionVersion> {
    console.log('API: Getting latest version for collection', collectionSlug);
    const params = new URLSearchParams();
    if (versionType) params.append('version_type', versionType);
    
    const response = await api.get(`/registry/collections/${collectionSlug}/latest-version?${params.toString()}`);
    console.log('API: Latest version response:', response.data);
    return response.data;
  },

  async getCollectionsWithVersions(
    includeInactive: boolean = false
  ): Promise<CodeCollection[]> {
    console.log('API: Getting collections with versions');
    const params = new URLSearchParams();
    if (includeInactive) params.append('include_inactive', 'true');
    
    const response = await api.get(`/registry/collections-with-versions?${params.toString()}`);
    console.log('API: Collections with versions response:', response.data);
    return response.data;
  },

  async getVersionCodebundles(
    collectionSlug: string, 
    versionName: string,
    limit?: number,
    offset?: number
  ): Promise<{version: CodeCollectionVersion, codebundles: VersionCodebundle[]}> {
    console.log('API: Getting codebundles for version', collectionSlug, versionName);
    const params = new URLSearchParams();
    if (limit) params.append('limit', limit.toString());
    if (offset) params.append('offset', offset.toString());
    
    const response = await api.get(`/registry/collections/${collectionSlug}/versions/${versionName}/codebundles?${params.toString()}`);
    console.log('API: Version codebundles response:', response.data);
    return response.data;
  },

  // Task Management endpoints
  async getTaskHistory(
    token: string,
    limit: number = 50,
    offset: number = 0,
    taskType?: string,
    status?: string
  ) {
    console.log('API: Getting task history');
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());
    if (taskType) params.append('task_type', taskType);
    if (status) params.append('status', status);
    
    const response = await api.get(`/task-management/tasks?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    console.log('API: Task history response:', response.data);
    return response.data;
  },

  async getRunningTasks(token: string) {
    console.log('API: Getting running tasks');
    const response = await api.get('/task-management/tasks/running', {
      headers: { Authorization: `Bearer ${token}` }
    });
    console.log('API: Running tasks response:', response.data);
    return response.data;
  },

  async getTaskStatus(token: string, taskId: string) {
    console.log('API: Getting task status for', taskId);
    const response = await api.get(`/task-management/tasks/${taskId}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    console.log('API: Task status response:', response.data);
    return response.data;
  },

  async getTaskStats(token: string, days: number = 7) {
    console.log('API: Getting task stats');
    const response = await api.get(`/task-management/stats?days=${days}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    console.log('API: Task stats response:', response.data);
    return response.data;
  }
};

export default api;