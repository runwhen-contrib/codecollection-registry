import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Box, Container, Typography, TextField, Button, Paper,
  CircularProgress, Alert, Collapse, FormControlLabel, Checkbox,
  ToggleButton, ToggleButtonGroup,
} from '@mui/material';
import {
  CheckCircle as CheckIcon,
  OpenInNew as ExternalLinkIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  RocketLaunch as RocketIcon,
  Chat as ChatIcon,
  Tune as TuneIcon,
} from '@mui/icons-material';
import { intakeApi, IntakeSearchMatch, IntakeExistingRequest } from '../services/api';

type Mode = 'simple' | 'explicit';

export default function IntakeWizard() {
  const location = useLocation();
  const [mode, setMode] = useState<Mode>('simple');

  // Core answers (question-driven)
  const [problemDescription, setProblemDescription] = useState('');
  const [platform, setPlatform] = useState('');
  const [healthyLooksLike, setHealthyLooksLike] = useState('');
  const [anythingElse, setAnythingElse] = useState('');

  // Explicit mode only
  const [explicitTasks, setExplicitTasks] = useState('');
  const [explicitVariables, setExplicitVariables] = useState('');

  // Meta
  const [contactEmail, setContactEmail] = useState('');
  const [contactOk, setContactOk] = useState(false);
  const [showContact, setShowContact] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ url: string; number: number } | null>(null);
  const [error, setError] = useState('');

  // Pre-fill from Chat "Request CodeBundle" or other entry points
  useEffect(() => {
    const state = location.state as { initialQuery?: string } | null;
    if (state?.initialQuery?.trim()) {
      setProblemDescription(state.initialQuery.trim());
    }
  }, [location.state]);

  const buildTitle = () => {
    const firstLine = problemDescription.split('\n')[0].trim();
    return firstLine.length > 60 ? firstLine.slice(0, 57) + '...' : firstLine || 'Skill Template request';
  };

  const buildDescription = () => {
    const parts: string[] = [problemDescription];
    if (platform.trim()) parts.push(`\n**Platform:** ${platform.trim()}`);
    if (healthyLooksLike.trim()) parts.push(`\n**What healthy looks like:** ${healthyLooksLike.trim()}`);
    if (anythingElse.trim()) parts.push(`\n**Additional context:** ${anythingElse.trim()}`);
    if (mode === 'explicit' && (explicitTasks.trim() || explicitVariables.trim())) {
      if (explicitTasks.trim()) parts.push(`\n**Suggested Tools:**\n${explicitTasks.trim()}`);
      if (explicitVariables.trim()) parts.push(`\n**Variables/config:**\n${explicitVariables.trim()}`);
    }
    return parts.join('\n');
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const description = buildDescription();
      let matches: IntakeSearchMatch[] = [];
      let existingRequests: IntakeExistingRequest[] = [];
      try {
        const searchRes = await intakeApi.search(description);
        matches = searchRes.matches;
        existingRequests = searchRes.existing_requests;
      } catch {
        // Search failed — continue
      }

      const res = await intakeApi.submit({
        title: buildTitle(),
        description,
        extra_context: undefined,
        contact_email: contactEmail.trim() || undefined,
        contact_ok: contactOk,
        matches,
        existing_requests: existingRequests,
      });
      setSubmitResult({ url: res.issue_url, number: res.issue_number });
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create request. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = problemDescription.trim().length > 0;

  if (submitResult) {
    return (
      <Container maxWidth="sm" sx={{ py: 4 }}>
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <CheckIcon color="success" sx={{ fontSize: 64, mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            Request Submitted
          </Typography>
          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            Issue #{submitResult.number} has been created. The designer will review
            your request and any existing coverage we found.
          </Typography>
          <Button
            variant="contained"
            startIcon={<ExternalLinkIcon />}
            href={submitResult.url}
            target="_blank"
            rel="noopener"
            sx={{ mr: 2 }}
          >
            View Issue
          </Button>
          <Button variant="outlined" onClick={() => window.location.reload()}>
            Submit Another
          </Button>
        </Paper>
      </Container>
    );
  }

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, textAlign: 'center' }}>
        <Typography variant="h4" gutterBottom>
          Request a Skill Template
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Describe the problem you're solving. The designer will figure out the rest.
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      <Paper sx={{ p: 4 }}>
        {/* Mode toggle */}
        <Box sx={{ mb: 3, display: 'flex', justifyContent: 'center' }}>
          <ToggleButtonGroup
            value={mode}
            exclusive
            onChange={(_, v) => v && setMode(v)}
            size="small"
          >
            <ToggleButton value="simple">
              <ChatIcon sx={{ mr: 0.5, fontSize: 18 }} />
              Simple
            </ToggleButton>
            <ToggleButton value="explicit">
              <TuneIcon sx={{ mr: 0.5, fontSize: 18 }} />
              Explicit
            </ToggleButton>
          </ToggleButtonGroup>
          <Typography variant="caption" sx={{ ml: 2, alignSelf: 'center', color: 'text.secondary' }}>
            {mode === 'simple'
              ? 'Describe naturally — the designer has autonomy'
              : 'Specify Tools and variables if you know them'}
          </Typography>
        </Box>

        {/* Question 1: Core */}
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1, color: 'text.primary' }}>
          What problem are you trying to solve?
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Describe the infrastructure task, health check, or troubleshooting scenario in your own words.
        </Typography>
        <TextField
          fullWidth
          multiline
          minRows={4}
          maxRows={10}
          placeholder="e.g., We need to monitor Kubernetes CronJobs — detect failed jobs, jobs that haven't run on schedule, and suspended CronJobs. Our team gets paged when things break and we need to triage quickly."
          value={problemDescription}
          onChange={(e) => setProblemDescription(e.target.value)}
          sx={{ mb: 3 }}
        />

        {/* Question 2: Platform */}
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1, color: 'text.primary' }}>
          What platform or infrastructure does this involve?
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Optional — we can often infer this from your description.
        </Typography>
        <TextField
          fullWidth
          placeholder="e.g., Kubernetes, AWS, Azure, GCP, Terraform..."
          value={platform}
          onChange={(e) => setPlatform(e.target.value)}
          sx={{ mb: 3 }}
        />

        {/* Question 3: Healthy */}
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1, color: 'text.primary' }}>
          What does "healthy" or "working" look like? How would you know something is wrong?
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          Optional — helps the designer scope the checks.
        </Typography>
        <TextField
          fullWidth
          multiline
          minRows={2}
          placeholder="e.g., CronJobs run on schedule, no failed jobs in the last 24h, no suspended CronJobs..."
          value={healthyLooksLike}
          onChange={(e) => setHealthyLooksLike(e.target.value)}
          sx={{ mb: 3 }}
        />

        {/* Question 4: Anything else */}
        <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1, color: 'text.primary' }}>
          Anything else the designer should know?
        </Typography>
        <TextField
          fullWidth
          multiline
          minRows={2}
          placeholder="Constraints, tools you use, how this fits into your workflow..."
          value={anythingElse}
          onChange={(e) => setAnythingElse(e.target.value)}
          sx={{ mb: 3 }}
        />

        {/* Explicit mode: tasks and variables */}
        <Collapse in={mode === 'explicit'}>
          <Box sx={{ mb: 3, pl: 1, borderLeft: 2, borderColor: 'divider' }}>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
              Only fill these if you already know the structure. Otherwise leave blank.
            </Typography>
            <TextField
              fullWidth
              multiline
              minRows={2}
              label="Suggested Tools (one per line)"
              placeholder="Check for failed CronJobs\nCheck for suspended CronJobs\n..."
              value={explicitTasks}
              onChange={(e) => setExplicitTasks(e.target.value)}
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              multiline
              minRows={1}
              label="Variables or config needed"
              placeholder="NAMESPACE, KUBECONFIG, ..."
              value={explicitVariables}
              onChange={(e) => setExplicitVariables(e.target.value)}
            />
          </Box>
        </Collapse>

        {/* Contact (collapsible) */}
        <Box sx={{ mb: 3 }}>
          <Button
            size="small"
            startIcon={showContact ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            onClick={() => setShowContact(!showContact)}
          >
            {showContact ? 'Hide' : 'Add contact info (optional)'}
          </Button>
          <Collapse in={showContact}>
            <Box sx={{ mt: 2 }}>
              <TextField
                fullWidth
                label="Email"
                placeholder="your@email.com"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                sx={{ mb: 1 }}
              />
              <FormControlLabel
                control={<Checkbox checked={contactOk} onChange={(e) => setContactOk(e.target.checked)} />}
                label="It's OK to reach out for clarification"
              />
            </Box>
          </Collapse>
        </Box>

        <Button
          fullWidth
          variant="contained"
          size="large"
          startIcon={submitting ? <CircularProgress size={20} color="inherit" /> : <RocketIcon />}
          onClick={handleSubmit}
          disabled={!canSubmit || submitting}
        >
          {submitting ? 'Searching & Submitting...' : 'Search & Submit'}
        </Button>
        <Typography variant="caption" display="block" sx={{ mt: 2, textAlign: 'center', color: 'text.secondary' }}>
          We search existing Skill Templates first, then create your request with the results attached for the designer.
        </Typography>
      </Paper>
    </Container>
  );
}
