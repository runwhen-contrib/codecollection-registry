import React, { useState, useEffect } from 'react';
import {
  Container,
  Typography,
  Card,
  CardContent,
  Box,
  Button,
  Tabs,
  Tab,
  Alert,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem
} from '@mui/material';

interface EnhancementLog {
  id: number;
  codebundle_id: number;
  codebundle_slug: string;
  status: string;
  model_used: string;
  service_provider: string;
  prompt_sent?: string;
  system_prompt?: string;
  ai_response_raw?: string;
  enhanced_description?: string;
  access_level?: string;
  iam_requirements?: string[];
  error_message?: string;
  processing_time_ms?: number;
  is_manually_edited: boolean;
  manual_notes?: string;
  created_at: string;
  updated_at?: string;
}

interface TaskExecution {
  id: number;
  task_id: string;
  task_name: string;
  status: string;
  result?: any;
  error_message?: string;
  traceback?: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
}

interface Stats {
  total_enhancements: number;
  successful: number;
  failed: number;
  manual_edits: number;
  success_rate: number;
  average_processing_time_ms: number;
}

const AIEnhancementAdmin: React.FC = () => {
  const [logs, setLogs] = useState<EnhancementLog[]>([]);
  const [taskExecutions, setTaskExecutions] = useState<TaskExecution[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [selectedLog, setSelectedLog] = useState<EnhancementLog | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingLog, setEditingLog] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState('enhancements');
  const [editForm, setEditForm] = useState({
    enhanced_description: '',
    access_level: 'unknown',
    iam_requirements: '',
    manual_notes: ''
  });

  const token = localStorage.getItem('token') || 'admin-dev-token';

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Import the configured API instance
      const { default: axios } = await import('axios');
      const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api/v1';
      const api = axios.create({
        baseURL: API_BASE_URL,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
      });

      // Fetch enhancement logs
      const logsResponse = await api.get('/admin/ai-enhancement/logs?limit=50');
      setLogs(logsResponse.data);

      // Fetch stats
      const statsResponse = await api.get('/admin/ai-enhancement/stats');
      setStats(statsResponse.data);

      // Fetch Celery task executions
      try {
        const tasksResponse = await api.get('/admin/task-executions?limit=50');
        setTaskExecutions(tasksResponse.data);
      } catch (taskErr) {
        console.warn('Failed to fetch task executions:', taskErr);
        setTaskExecutions([]);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  const handleManualEdit = async (logId: number) => {
    try {
      const { default: axios } = await import('axios');
      const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api/v1';
      const api = axios.create({
        baseURL: API_BASE_URL,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
      });

      await api.put(`/admin/ai-enhancement/logs/${logId}/manual-edit`, {
        enhanced_description: editForm.enhanced_description,
        access_level: editForm.access_level,
        iam_requirements: editForm.iam_requirements.split('\n').filter(req => req.trim()),
        manual_notes: editForm.manual_notes
      });
      
      setEditingLog(null);
      fetchData(); // Refresh data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save edit');
    }
  };

  const enhanceCodebundle = async (codebundleId: number) => {
    try {
      setLoading(true);
      const { default: axios } = await import('axios');
      const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api/v1';
      const api = axios.create({
        baseURL: API_BASE_URL,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
      });

      await api.post(`/admin/ai-enhancement/enhance/${codebundleId}`);
      
      fetchData(); // Refresh data
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to enhance codebundle');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return '✅';
      case 'failed': return '❌';
      case 'pending': return '⏳';
      case 'manual_override': return '✏️';
      default: return '⚠️';
    }
  };

  const getStatusBadge = (status: string) => {
    const colors = {
      'SUCCESS': 'bg-green-100 text-green-800',
      'FAILURE': 'bg-red-100 text-red-800',
      'PENDING': 'bg-yellow-100 text-yellow-800',
      'RETRY': 'bg-blue-100 text-blue-800',
      'REVOKED': 'bg-gray-100 text-gray-800'
    };
    
    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status as keyof typeof colors] || 'bg-gray-100 text-gray-800'}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="container mx-auto p-6 space-y-6" style={{ maxWidth: '1200px' }}>
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">AI Enhancement Administration</h1>
        <button 
          onClick={fetchData} 
          disabled={loading}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? '🔄 Loading...' : '🔄 Refresh'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded p-4">
          <div className="flex items-center">
            <span className="text-red-500 mr-2">⚠️</span>
            <span className="text-red-800">{error}</span>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white border rounded-lg p-4 shadow">
            <div className="flex items-center space-x-2">
              <span className="text-blue-500">⚡</span>
              <div>
                <p className="text-sm font-medium text-gray-600">Total Enhancements</p>
                <p className="text-2xl font-bold">{stats.total_enhancements}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white border rounded-lg p-4 shadow">
            <div className="flex items-center space-x-2">
              <span className="text-green-500">✅</span>
              <div>
                <p className="text-sm font-medium text-gray-600">Success Rate</p>
                <p className="text-2xl font-bold">{stats.success_rate.toFixed(1)}%</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white border rounded-lg p-4 shadow">
            <div className="flex items-center space-x-2">
              <span className="text-blue-500">✏️</span>
              <div>
                <p className="text-sm font-medium text-gray-600">Manual Edits</p>
                <p className="text-2xl font-bold">{stats.manual_edits}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white border rounded-lg p-4 shadow">
            <div className="flex items-center space-x-2">
              <span className="text-yellow-500">⏱️</span>
              <div>
                <p className="text-sm font-medium text-gray-600">Avg Time</p>
                <p className="text-2xl font-bold">{stats.average_processing_time_ms}ms</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white border rounded-lg shadow">
        <div className="border-b">
          <nav className="flex space-x-8 px-6">
            {['enhancements', 'celery'].map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab === 'enhancements' && '⚙️ AI Enhancement Logs'}
                {tab === 'celery' && '🗄️ Celery Task Logs'}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {/* AI Enhancement Logs Tab */}
          {activeTab === 'enhancements' && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center">
                <span className="mr-2">⚙️</span>
                AI Enhancement Logs
              </h2>
              
              <div className="space-y-4">
                {logs.map((log) => (
                  <div key={log.id} className="border border-l-4 border-l-blue-500 rounded-lg p-4 bg-gray-50">
                    <div className="flex justify-between items-start">
                      <div className="space-y-2 flex-1">
                        <div className="flex items-center space-x-2">
                          <span>{getStatusIcon(log.status)}</span>
                          <span className="font-medium">{log.codebundle_slug}</span>
                          <span className="px-2 py-1 bg-gray-200 rounded text-xs">{log.model_used}</span>
                          {log.is_manually_edited && (
                            <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">Manually Edited</span>
                          )}
                        </div>
                        
                        <p className="text-sm text-gray-600">
                          {log.enhanced_description || 'No description available'}
                        </p>
                        
                        <div className="flex items-center space-x-4 text-xs text-gray-500">
                          <span>Access: {log.access_level || 'unknown'}</span>
                          <span>IAM: {log.iam_requirements?.length || 0} requirements</span>
                          <span>Time: {log.processing_time_ms}ms</span>
                          <span>{new Date(log.created_at).toLocaleString()}</span>
                        </div>
                        
                        {log.error_message && (
                          <div className="bg-red-50 border border-red-200 rounded p-2">
                            <p className="text-red-800 text-xs">{log.error_message}</p>
                          </div>
                        )}
                      </div>
                      
                      <div className="flex space-x-2 ml-4">
                        <button
                          onClick={() => setSelectedLog(log)}
                          className="px-3 py-1 bg-gray-200 hover:bg-gray-300 rounded text-sm"
                        >
                          👁️ View
                        </button>
                        <button
                          onClick={() => {
                            setEditingLog(log.id);
                            setEditForm({
                              enhanced_description: log.enhanced_description || '',
                              access_level: log.access_level || 'unknown',
                              iam_requirements: log.iam_requirements?.join('\n') || '',
                              manual_notes: log.manual_notes || ''
                            });
                          }}
                          className="px-3 py-1 bg-blue-200 hover:bg-blue-300 rounded text-sm"
                        >
                          ✏️ Edit
                        </button>
                        <button
                          onClick={() => enhanceCodebundle(log.codebundle_id)}
                          className="px-3 py-1 bg-green-200 hover:bg-green-300 rounded text-sm"
                        >
                          ▶️ Re-run
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Celery Task Logs Tab */}
          {activeTab === 'celery' && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold flex items-center">
                <span className="mr-2">🗄️</span>
                Celery Task Executions
              </h2>
              
              <div className="space-y-4">
                {taskExecutions.map((task) => (
                  <div key={task.id} className="border border-l-4 border-l-green-500 rounded-lg p-4 bg-gray-50">
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        {getStatusBadge(task.status)}
                        <span className="font-medium">{task.task_name}</span>
                      </div>
                      
                      <p className="text-sm text-gray-600 font-mono">
                        Task ID: {task.task_id}
                      </p>
                      
                      <div className="flex items-center space-x-4 text-xs text-gray-500">
                        <span>Started: {new Date(task.started_at).toLocaleString()}</span>
                        {task.completed_at && (
                          <span>Completed: {new Date(task.completed_at).toLocaleString()}</span>
                        )}
                            {task.duration_seconds && (
                              <span>Duration: {task.duration_seconds}s</span>
                            )}
                      </div>
                      
                      {task.error_message && (
                        <div className="bg-red-50 border border-red-200 rounded p-2">
                          <p className="text-red-800 text-xs">{task.error_message}</p>
                        </div>
                      )}
                      
                      {task.traceback && (
                        <details className="text-xs">
                          <summary className="cursor-pointer text-gray-600">Show Traceback</summary>
                          <pre className="mt-2 p-2 bg-gray-100 rounded text-xs overflow-x-auto">
                            {task.traceback}
                          </pre>
                        </details>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>

      {/* Manual Edit Modal */}
      {editingLog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">Manual Edit Enhancement</h2>
            </div>
            
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">Enhanced Description:</label>
                <textarea
                  value={editForm.enhanced_description}
                  onChange={(e) => setEditForm({...editForm, enhanced_description: e.target.value})}
                  className="w-full h-32 p-3 border rounded"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">Access Level:</label>
                <select
                  value={editForm.access_level}
                  onChange={(e) => setEditForm({...editForm, access_level: e.target.value})}
                  className="w-full p-2 border rounded"
                >
                  <option value="unknown">Unknown</option>
                  <option value="read-only">Read Only</option>
                  <option value="read-write">Read Write</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">IAM Requirements (one per line):</label>
                <textarea
                  value={editForm.iam_requirements}
                  onChange={(e) => setEditForm({...editForm, iam_requirements: e.target.value})}
                  className="w-full h-32 p-3 border rounded"
                  placeholder="ec2:DescribeInstances&#10;s3:GetObject&#10;..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">Manual Notes:</label>
                <textarea
                  value={editForm.manual_notes}
                  onChange={(e) => setEditForm({...editForm, manual_notes: e.target.value})}
                  className="w-full h-20 p-3 border rounded"
                />
              </div>
              
              <div className="flex justify-end space-x-2 pt-4">
                <button 
                  onClick={() => setEditingLog(null)}
                  className="px-4 py-2 border rounded hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button 
                  onClick={() => handleManualEdit(editingLog)}
                  className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                >
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIEnhancementAdmin;