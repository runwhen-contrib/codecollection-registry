import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, Container, Typography, Stepper, Step, StepLabel,
  TextField, Button, Paper, Chip, Card, CardContent,
  CircularProgress, Alert, AlertTitle, IconButton,
  Autocomplete, List, ListItem, ListItemText, ListItemIcon,
  Divider, Link, Collapse,
} from '@mui/material';
import {
  Search as SearchIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  CheckCircle as CheckIcon,
  Warning as WarningIcon,
  OpenInNew as ExternalLinkIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  RocketLaunch as RocketIcon,
} from '@mui/icons-material';
import {
  intakeApi,
  IntakeSearchMatch,
  IntakeExistingRequest,
  IntakeDesignSpec,
} from '../services/api';

const STEPS = ['Describe', 'Search Results', 'Specify', 'Review & Submit'];

interface TaskEntry {
  name: string;
  checks: string;
}

interface EnvVarEntry {
  name: string;
  description: string;
  example: string;
}

interface SecretEntry {
  name: string;
  description: string;
}

export default function IntakeWizard() {
  const [activeStep, setActiveStep] = useState(0);

  // Step 1: Describe
  const [description, setDescription] = useState('');
  const [platform, setPlatform] = useState('');
  const [platforms, setPlatforms] = useState<string[]>([]);

  // Step 2: Search results
  const [searching, setSearching] = useState(false);
  const [matches, setMatches] = useState<IntakeSearchMatch[]>([]);
  const [existingRequests, setExistingRequests] = useState<IntakeExistingRequest[]>([]);
  const [suggestedPlatform, setSuggestedPlatform] = useState('');
  const [matchesExpanded, setMatchesExpanded] = useState(true);

  // Step 3: Specify
  const [bundleName, setBundleName] = useState('');
  const [purpose, setPurpose] = useState('');
  const [tasks, setTasks] = useState<TaskEntry[]>([{ name: '', checks: '' }]);
  const [resourceTypes, setResourceTypes] = useState('');
  const [envVars, setEnvVars] = useState<EnvVarEntry[]>([]);
  const [secrets, setSecrets] = useState<SecretEntry[]>([]);
  const [toolsRequired, setToolsRequired] = useState('');
  const [targetCollection, setTargetCollection] = useState('rw-cli-codecollection');

  // Step 4: Submit
  const [contactEmail, setContactEmail] = useState('');
  const [coverageNotes, setCoverageNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ url: string; number: number } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    intakeApi.getPlatforms().then((res) => setPlatforms(res.platforms)).catch(() => {});
  }, []);

  // Step 1 → 2: Search
  const handleSearch = useCallback(async () => {
    setSearching(true);
    setError('');
    try {
      const res = await intakeApi.search(description, platform || undefined);
      setMatches(res.matches);
      setExistingRequests(res.existing_requests);
      if (res.suggested_platform && !platform) {
        setSuggestedPlatform(res.suggested_platform);
        setPlatform(res.suggested_platform);
      }
      setPurpose(description);
      setActiveStep(1);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Search failed. You can skip to specify details manually.');
      setActiveStep(1);
    } finally {
      setSearching(false);
    }
  }, [description, platform]);

  // Step 2 → 3: Nothing found, proceed to specify
  const handleProceedToSpecify = () => {
    const notes = matches.length > 0
      ? `Searched and found ${matches.length} partially related bundle(s), but user indicated none fully solve the need.`
      : 'No existing CodeBundles found for this request.';
    setCoverageNotes(notes);

    if (!bundleName) {
      const prefix = platform ? platform.toLowerCase().replace(/\s+/g, '-') : 'generic';
      const words = description.toLowerCase().split(/\s+/).filter((w) => w.length > 2).slice(0, 3);
      setBundleName(`${prefix}-${words.join('-') || 'healthcheck'}`);
    }
    setActiveStep(2);
  };

  // Step 3 → 4: Move to review
  const handleReview = () => {
    setActiveStep(3);
  };

  // Step 4: Submit
  const handleSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const spec: IntakeDesignSpec = {
        codebundle_name: bundleName,
        target_collection: targetCollection,
        platform,
        purpose,
        tasks: tasks.filter((t) => t.name || t.checks),
        resource_types: resourceTypes.split(',').map((s) => s.trim()).filter(Boolean),
        env_vars: envVars.filter((v) => v.name),
        secrets: secrets.filter((s) => s.name),
        tools_required: toolsRequired.split(',').map((s) => s.trim()).filter(Boolean),
        related_bundles: matches.slice(0, 3).map((m) => `${m.collection_slug}/${m.slug}`),
        user_description: description,
        coverage_notes: coverageNotes,
      };
      const res = await intakeApi.submit(spec, contactEmail || undefined);
      setSubmitResult({ url: res.issue_url, number: res.issue_number });
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to create issue. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // Task list helpers
  const addTask = () => setTasks([...tasks, { name: '', checks: '' }]);
  const removeTask = (i: number) => setTasks(tasks.filter((_, idx) => idx !== i));
  const updateTask = (i: number, field: keyof TaskEntry, value: string) => {
    const updated = [...tasks];
    updated[i] = { ...updated[i], [field]: value };
    setTasks(updated);
  };

  // Env var helpers
  const addEnvVar = () => setEnvVars([...envVars, { name: '', description: '', example: '' }]);
  const removeEnvVar = (i: number) => setEnvVars(envVars.filter((_, idx) => idx !== i));
  const updateEnvVar = (i: number, field: keyof EnvVarEntry, value: string) => {
    const updated = [...envVars];
    updated[i] = { ...updated[i], [field]: value };
    setEnvVars(updated);
  };

  // Secret helpers
  const addSecret = () => setSecrets([...secrets, { name: '', description: '' }]);
  const removeSecret = (i: number) => setSecrets(secrets.filter((_, idx) => idx !== i));
  const updateSecret = (i: number, field: keyof SecretEntry, value: string) => {
    const updated = [...secrets];
    updated[i] = { ...updated[i], [field]: value };
    setSecrets(updated);
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, textAlign: 'center' }}>
        <Typography variant="h4" gutterBottom>
          Request a CodeBundle
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Describe what you need automated, and we'll check existing coverage
          before creating a structured request.
        </Typography>
      </Box>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {error && (
        <Alert severity="warning" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {/* ─── Step 0: Describe ─── */}
      {activeStep === 0 && (
        <Paper sx={{ p: 4 }}>
          <Typography variant="h6" gutterBottom>
            What do you need automated?
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Describe the infrastructure task, health check, or troubleshooting
            scenario you need. Be as specific as possible — include the platform,
            resource types, and what "healthy" looks like.
          </Typography>

          <TextField
            fullWidth
            multiline
            minRows={4}
            maxRows={10}
            placeholder="e.g., I need to monitor Kubernetes CronJobs — check for failed jobs, jobs that haven't run on schedule, and suspended CronJobs. Should work across namespaces with configurable filters."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            sx={{ mb: 3 }}
          />

          <Autocomplete
            freeSolo
            options={platforms}
            value={platform}
            onInputChange={(_, v) => setPlatform(v)}
            renderInput={(params) => (
              <TextField {...params} label="Platform (optional)" placeholder="e.g., Kubernetes" />
            )}
            sx={{ mb: 3 }}
          />

          <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="contained"
              size="large"
              startIcon={searching ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
              onClick={handleSearch}
              disabled={!description.trim() || searching}
            >
              {searching ? 'Searching...' : 'Search Existing Coverage'}
            </Button>
          </Box>
        </Paper>
      )}

      {/* ─── Step 1: Search Results ─── */}
      {activeStep === 1 && (
        <Box>
          {matches.length > 0 && (
            <Paper sx={{ p: 3, mb: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="h6">
                  Existing CodeBundles ({matches.length})
                </Typography>
                <IconButton size="small" onClick={() => setMatchesExpanded(!matchesExpanded)}>
                  {matchesExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </IconButton>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                We found these existing bundles that may address your need.
                If one solves your problem, you're all set!
              </Typography>

              <Collapse in={matchesExpanded}>
                {matches.map((m, i) => (
                  <Card key={i} variant="outlined" sx={{ mb: 2 }}>
                    <CardContent>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Typography variant="subtitle1" fontWeight={600}>
                          {m.display_name}
                        </Typography>
                        {m.relevance_score > 0 && (
                          <Chip
                            label={`${Math.round(m.relevance_score * 100)}% match`}
                            size="small"
                            color={m.relevance_score > 0.7 ? 'success' : 'default'}
                          />
                        )}
                      </Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                        {m.description}
                      </Typography>
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
                        {m.platform && <Chip label={m.platform} size="small" variant="outlined" />}
                        <Chip label={m.collection_slug} size="small" variant="outlined" />
                        {m.tags.slice(0, 4).map((t) => (
                          <Chip key={t} label={t} size="small" />
                        ))}
                      </Box>
                      {m.tasks.length > 0 && (
                        <Typography variant="body2" color="text.secondary">
                          Tasks: {m.tasks.slice(0, 5).join(', ')}
                          {m.tasks.length > 5 && ` (+${m.tasks.length - 5} more)`}
                        </Typography>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </Collapse>
            </Paper>
          )}

          {existingRequests.length > 0 && (
            <Paper sx={{ p: 3, mb: 3 }}>
              <Typography variant="h6" gutterBottom>
                Open Requests ({existingRequests.length})
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                These open issues may be requesting the same thing. Consider
                commenting on one instead of filing a duplicate.
              </Typography>
              <List dense>
                {existingRequests.map((r) => (
                  <ListItem key={r.number}>
                    <ListItemIcon><WarningIcon color="warning" /></ListItemIcon>
                    <ListItemText
                      primary={
                        <Link href={r.url} target="_blank" rel="noopener">
                          #{r.number} — {r.title} <ExternalLinkIcon sx={{ fontSize: 14, ml: 0.5 }} />
                        </Link>
                      }
                      secondary={r.created_at ? `Created ${r.created_at}` : undefined}
                    />
                  </ListItem>
                ))}
              </List>
            </Paper>
          )}

          {matches.length === 0 && existingRequests.length === 0 && (
            <Alert severity="info" sx={{ mb: 3 }}>
              <AlertTitle>No existing coverage found</AlertTitle>
              This looks like a new need. Let's define the requirements so the
              team can build it.
            </Alert>
          )}

          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button onClick={() => setActiveStep(0)}>Back</Button>
            <Button
              variant="contained"
              onClick={handleProceedToSpecify}
            >
              {matches.length > 0 ? "None of these — I need something new" : "Define Requirements"}
            </Button>
          </Box>
        </Box>
      )}

      {/* ─── Step 2: Specify ─── */}
      {activeStep === 2 && (
        <Paper sx={{ p: 4 }}>
          <Typography variant="h6" gutterBottom>
            Define the CodeBundle
          </Typography>

          <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
            <TextField
              fullWidth
              label="Bundle Name"
              placeholder="e.g., k8s-cronjob-healthcheck"
              value={bundleName}
              onChange={(e) => setBundleName(e.target.value)}
              helperText="Convention: {platform}-{resource}-{purpose}"
            />
            <Autocomplete
              freeSolo
              options={platforms}
              value={platform}
              onInputChange={(_, v) => setPlatform(v)}
              sx={{ minWidth: 200 }}
              renderInput={(params) => <TextField {...params} label="Platform" />}
            />
          </Box>

          <TextField
            fullWidth
            label="Purpose"
            multiline
            minRows={2}
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            sx={{ mb: 3 }}
          />

          {/* Tasks */}
          <Typography variant="subtitle2" gutterBottom>
            Tasks (what should this bundle check or do?)
          </Typography>
          {tasks.map((t, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'flex-start' }}>
              <TextField
                size="small"
                label={`Task ${i + 1} name`}
                value={t.name}
                onChange={(e) => updateTask(i, 'name', e.target.value)}
                sx={{ flex: 1 }}
              />
              <TextField
                size="small"
                label="What it checks"
                value={t.checks}
                onChange={(e) => updateTask(i, 'checks', e.target.value)}
                sx={{ flex: 2 }}
              />
              {tasks.length > 1 && (
                <IconButton size="small" onClick={() => removeTask(i)}><DeleteIcon /></IconButton>
              )}
            </Box>
          ))}
          <Button size="small" startIcon={<AddIcon />} onClick={addTask} sx={{ mb: 3 }}>
            Add Task
          </Button>

          <Divider sx={{ my: 2 }} />

          <TextField
            fullWidth
            label="Resource Types"
            placeholder="e.g., CronJob, Job, Namespace"
            value={resourceTypes}
            onChange={(e) => setResourceTypes(e.target.value)}
            helperText="Comma-separated Kubernetes/cloud resource types"
            sx={{ mb: 3 }}
          />

          <TextField
            fullWidth
            label="Tools / CLIs Required"
            placeholder="e.g., kubectl, jq, aws"
            value={toolsRequired}
            onChange={(e) => setToolsRequired(e.target.value)}
            helperText="Comma-separated"
            sx={{ mb: 3 }}
          />

          {/* Env Vars */}
          <Typography variant="subtitle2" gutterBottom>
            Environment Variables (user-configurable inputs)
          </Typography>
          {envVars.map((v, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, mb: 1 }}>
              <TextField size="small" label="Name" placeholder="NAMESPACE" value={v.name}
                onChange={(e) => updateEnvVar(i, 'name', e.target.value)} sx={{ flex: 1 }} />
              <TextField size="small" label="Description" value={v.description}
                onChange={(e) => updateEnvVar(i, 'description', e.target.value)} sx={{ flex: 2 }} />
              <TextField size="small" label="Example" value={v.example}
                onChange={(e) => updateEnvVar(i, 'example', e.target.value)} sx={{ flex: 1 }} />
              <IconButton size="small" onClick={() => removeEnvVar(i)}><DeleteIcon /></IconButton>
            </Box>
          ))}
          <Button size="small" startIcon={<AddIcon />} onClick={addEnvVar} sx={{ mb: 3 }}>
            Add Variable
          </Button>

          {/* Secrets */}
          <Typography variant="subtitle2" gutterBottom>
            Secrets (credentials needed)
          </Typography>
          {secrets.map((s, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, mb: 1 }}>
              <TextField size="small" label="Name" placeholder="kubeconfig" value={s.name}
                onChange={(e) => updateSecret(i, 'name', e.target.value)} sx={{ flex: 1 }} />
              <TextField size="small" label="Description" value={s.description}
                onChange={(e) => updateSecret(i, 'description', e.target.value)} sx={{ flex: 2 }} />
              <IconButton size="small" onClick={() => removeSecret(i)}><DeleteIcon /></IconButton>
            </Box>
          ))}
          <Button size="small" startIcon={<AddIcon />} onClick={addSecret} sx={{ mb: 3 }}>
            Add Secret
          </Button>

          <Divider sx={{ my: 2 }} />

          <TextField
            fullWidth
            label="Target CodeCollection"
            value={targetCollection}
            onChange={(e) => setTargetCollection(e.target.value)}
            helperText="Which CodeCollection should this bundle live in?"
            sx={{ mb: 3 }}
          />

          <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
            <Button onClick={() => setActiveStep(1)}>Back</Button>
            <Button
              variant="contained"
              onClick={handleReview}
              disabled={!bundleName.trim() || !purpose.trim() || tasks.every((t) => !t.name && !t.checks)}
            >
              Review
            </Button>
          </Box>
        </Paper>
      )}

      {/* ─── Step 3: Review & Submit ─── */}
      {activeStep === 3 && (
        <Box>
          {submitResult ? (
            <Paper sx={{ p: 4, textAlign: 'center' }}>
              <CheckIcon color="success" sx={{ fontSize: 64, mb: 2 }} />
              <Typography variant="h5" gutterBottom>
                Request Submitted
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                Issue #{submitResult.number} has been created in codebundle-farm.
                The team will review your Design Spec and begin implementation.
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
          ) : (
            <Paper sx={{ p: 4 }}>
              <Typography variant="h6" gutterBottom>
                Review Your Request
              </Typography>

              <Card variant="outlined" sx={{ mb: 3, bgcolor: 'background.default' }}>
                <CardContent>
                  <Typography variant="subtitle2" color="text.secondary">CodeBundle Name</Typography>
                  <Typography variant="h6" sx={{ mb: 1 }}>{bundleName}</Typography>

                  <Typography variant="subtitle2" color="text.secondary">Platform</Typography>
                  <Typography sx={{ mb: 1 }}>{platform || 'Not specified'}</Typography>

                  <Typography variant="subtitle2" color="text.secondary">Purpose</Typography>
                  <Typography sx={{ mb: 1 }}>{purpose}</Typography>

                  <Typography variant="subtitle2" color="text.secondary">Tasks</Typography>
                  <List dense>
                    {tasks.filter((t) => t.name || t.checks).map((t, i) => (
                      <ListItem key={i} disablePadding>
                        <ListItemText
                          primary={t.name || `Task ${i + 1}`}
                          secondary={t.checks}
                        />
                      </ListItem>
                    ))}
                  </List>

                  {resourceTypes && (
                    <>
                      <Typography variant="subtitle2" color="text.secondary">Resource Types</Typography>
                      <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
                        {resourceTypes.split(',').filter(Boolean).map((r) => (
                          <Chip key={r.trim()} label={r.trim()} size="small" />
                        ))}
                      </Box>
                    </>
                  )}

                  {envVars.filter((v) => v.name).length > 0 && (
                    <>
                      <Typography variant="subtitle2" color="text.secondary">Environment Variables</Typography>
                      {envVars.filter((v) => v.name).map((v, i) => (
                        <Typography key={i} variant="body2">
                          <code>{v.name}</code> — {v.description} {v.example && `(e.g., ${v.example})`}
                        </Typography>
                      ))}
                    </>
                  )}

                  {secrets.filter((s) => s.name).length > 0 && (
                    <>
                      <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1 }}>Secrets</Typography>
                      {secrets.filter((s) => s.name).map((s, i) => (
                        <Typography key={i} variant="body2">
                          <code>{s.name}</code> — {s.description}
                        </Typography>
                      ))}
                    </>
                  )}

                  <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1 }}>Target Collection</Typography>
                  <Typography variant="body2">{targetCollection}</Typography>
                </CardContent>
              </Card>

              <TextField
                fullWidth
                label="Contact Email (optional)"
                placeholder="your@email.com"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                helperText="If you'd like to be notified when the bundle is ready"
                sx={{ mb: 3 }}
              />

              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Button onClick={() => setActiveStep(2)}>Back to Edit</Button>
                <Button
                  variant="contained"
                  size="large"
                  startIcon={submitting ? <CircularProgress size={20} color="inherit" /> : <RocketIcon />}
                  onClick={handleSubmit}
                  disabled={submitting}
                >
                  {submitting ? 'Submitting...' : 'Submit Request'}
                </Button>
              </Box>
            </Paper>
          )}
        </Box>
      )}
    </Container>
  );
}
