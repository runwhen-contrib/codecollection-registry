import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { apiService } from '../services/api';

interface ChartData {
  week: string;
  tasks: number;
}

const TaskGrowthChart: React.FC = () => {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';
  const [data, setData] = useState<ChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalTasks, setTotalTasks] = useState(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Use the faster cached version for production
        const response = await apiService.getTasksByWeek();
        
        // Transform data for chart
        const chartData: ChartData[] = response.weeks.map((month: string, index: number) => ({
          week: formatMonthLabel(month),
          tasks: response.cumulative[index],
        }));
        
        setData(chartData);
        setTotalTasks(response.total_tasks);
        setError(null);
      } catch (err: any) {
        console.error('Error fetching task growth data:', err);
        setError('Failed to load task growth data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const formatMonthLabel = (dateStr: string): string => {
    const date = new Date(dateStr);
    const month = date.toLocaleDateString('en-US', { month: 'short' });
    const year = date.getFullYear();
    return `${month} '${year.toString().slice(2)}`;
  };

  if (loading) {
    return (
      <Card>
        <CardContent>
          <Box display="flex" justifyContent="center" alignItems="center" minHeight="300px">
            <CircularProgress />
          </Box>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardContent>
          <Alert severity="info">{error}</Alert>
        </CardContent>
      </Card>
    );
  }

  // Show all months (18 months is reasonable for x-axis)
  const labelInterval = 0;

  return (
    <Card>
      <CardContent>
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
            Task Library Growth
          </Typography>
        </Box>

        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorTasks" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#FF6B35" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#FF6B35" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={isDark ? '#333' : '#e0e0e0'} />
            <XAxis 
              dataKey="week" 
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              interval={labelInterval}
              angle={-45}
              textAnchor="end"
              height={60}
            />
            <YAxis 
              tick={{ fontSize: 12, fill: theme.palette.text.secondary }}
              tickFormatter={(value) => value.toLocaleString()}
            />
            <Tooltip 
              formatter={(value: number | undefined) => [`${(value ?? 0).toLocaleString()} tasks`, 'Total Tasks']}
              contentStyle={{
                backgroundColor: isDark ? '#2a2a2a' : 'rgba(255, 255, 255, 0.95)',
                border: `1px solid ${isDark ? '#444' : '#ccc'}`,
                borderRadius: '4px',
                color: theme.palette.text.primary,
              }}
            />
            <Area 
              type="monotone" 
              dataKey="tasks" 
              stroke="#FF6B35" 
              strokeWidth={2}
              fillOpacity={1}
              fill="url(#colorTasks)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
};

export default TaskGrowthChart;
