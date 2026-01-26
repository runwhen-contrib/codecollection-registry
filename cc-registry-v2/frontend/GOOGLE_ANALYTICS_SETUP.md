# Google Analytics Setup

## Quick Setup (5 minutes)

### 1. Get Your Google Analytics Measurement ID

1. Go to [Google Analytics](https://analytics.google.com/)
2. Create a new property (or use existing)
3. Set up a Web Data Stream
4. Copy your **Measurement ID** (format: `G-XXXXXXXXXX`)

### 2. Configure the App

Add to your `.env` file (frontend):

```bash
# For local development
REACT_APP_GA_MEASUREMENT_ID=G-XXXXXXXXXX

# Optional: disable in development
REACT_APP_ENABLE_ANALYTICS=false
```

For Kubernetes, add to your ConfigMap or deployment:

```yaml
env:
- name: REACT_APP_GA_MEASUREMENT_ID
  value: "G-XXXXXXXXXX"
```

### 3. Rebuild Frontend

```bash
cd frontend
npm run build

# Or in Docker
docker-compose build frontend
```

That's it! Analytics will now track:
- ✅ Page views automatically
- ✅ Single Page App (SPA) navigation
- ✅ Custom events (optional)

---

## Optional: Track Custom Events

Use the analytics helper functions in your components:

```typescript
import { trackCodebundleView, trackSearch, trackAddToCart } from './utils/analytics';

// Track when user views a codebundle
trackCodebundleView('my-codebundle', 'runwhen-contrib');

// Track searches
trackSearch('kubernetes', 15); // query, results count

// Track adding to cart
trackAddToCart('my-codebundle');
```

### Example: Track Codebundle Page Views

In `CodeBundleDetail.tsx`:

```typescript
import { trackCodebundleView } from '../utils/analytics';

useEffect(() => {
  if (codebundle) {
    trackCodebundleView(codebundle.slug, codebundle.codecollection?.slug || '');
  }
}, [codebundle]);
```

### Example: Track Search

In `AllTasks.tsx`:

```typescript
import { trackSearch } from '../utils/analytics';

const handleSearch = (query: string) => {
  setSearchTerm(query);
  trackSearch(query, filteredTasks.length);
};
```

---

## What Gets Tracked Automatically

✅ **Page Views**: Every route change  
✅ **Session Duration**: How long users stay  
✅ **Bounce Rate**: Single-page visits  
✅ **Traffic Sources**: Where users come from  
✅ **Devices**: Desktop, mobile, tablet  
✅ **Geographic Location**: Country, city  

---

## Privacy Considerations

The implementation:
- ✅ Uses Google Analytics 4 (privacy-focused)
- ✅ Respects Do Not Track browser settings
- ✅ No personally identifiable information (PII) sent
- ✅ Can be disabled via environment variable

**Add to your privacy policy:**
> This site uses Google Analytics to understand how visitors use the site. Analytics collects anonymous usage data including pages visited, session duration, and geographic region.

---

## Verify It's Working

1. Visit your site: `https://your-registry.com`
2. Open Google Analytics dashboard
3. Go to **Reports** → **Realtime**
4. You should see your visit in real-time!

---

## Disable in Development

To prevent development traffic from skewing analytics:

```bash
# .env.local
REACT_APP_GA_MEASUREMENT_ID=
# Or
REACT_APP_ENABLE_ANALYTICS=false
```

Or wrap the script in a conditional:

```html
<!-- Only load in production -->
%REACT_APP_GA_MEASUREMENT_ID% && (
  <script>
    // GA code here
  </script>
)
```

---

## Advanced: Track Backend Events

If you want to track backend events (e.g., API usage), use Google Analytics Measurement Protocol:

```python
# backend/app/services/analytics.py
import requests

def track_backend_event(client_id: str, event_name: str, params: dict):
    """Send server-side events to Google Analytics"""
    if not settings.GA_MEASUREMENT_ID or not settings.GA_API_SECRET:
        return
    
    url = f"https://www.google-analytics.com/mp/collect?measurement_id={settings.GA_MEASUREMENT_ID}&api_secret={settings.GA_API_SECRET}"
    
    payload = {
        "client_id": client_id,
        "events": [{
            "name": event_name,
            "params": params
        }]
    }
    
    requests.post(url, json=payload)

# Usage
track_backend_event(
    client_id="user-123",
    event_name="codebundle_enhance",
    params={"codebundle_slug": "my-bundle", "success": True}
)
```

---

## Troubleshooting

**Not seeing data?**
1. Check browser console for errors
2. Verify `REACT_APP_GA_MEASUREMENT_ID` is set
3. Wait 24-48 hours for full data (Realtime is instant though)
4. Check ad blockers aren't blocking GA
5. Verify domain is registered in GA property settings

**Data looks wrong?**
1. Filter out internal traffic (your IP) in GA settings
2. Enable debug mode: `gtag('config', 'GA_ID', {debug_mode: true})`
3. Use GA Debug Chrome extension to see events live
