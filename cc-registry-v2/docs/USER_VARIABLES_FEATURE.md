# User Variables Feature

**Status:** ✅ Implemented (2026-01-24)

## Overview

The User Variables feature automatically parses and displays `RW.Core.Import User Variable` declarations from Robot Framework files in codebundles. This provides users with clear documentation of what variables need to be configured to use a codebundle.

## 📋 What Was Implemented

### 1. Database Schema

Added `user_variables` field to the `codebundles` table:

```sql
-- Stores array of user variable objects
user_variables JSONB DEFAULT '[]'::jsonb

-- Each variable object contains:
{
  "name": "VARIABLE_NAME",
  "type": "string",
  "description": "Human-readable description",
  "pattern": "\\w*",  // Validation regex
  "example": "example-value",
  "default": null  // Optional default value
}
```

**Migration:** `database/migrations/005_add_user_variables.sql`

### 2. Parser Function

Created `parse_user_variables()` in `backend/app/tasks/fixed_parser.py`:

```python
def parse_user_variables(content: str) -> List[Dict[str, Any]]:
    """
    Parse RW.Core.Import User Variable calls from Robot file content.
    
    Extracts:
    - Variable name
    - Type (string, integer, etc.)
    - Description
    - Pattern (validation regex)
    - Example value
    - Default value (if provided)
    """
```

**How it works:**
1. Scans Robot file content for `RW.Core.Import User Variable` patterns
2. Extracts variable name from `${VAR_NAME}=` assignment
3. Parses continuation lines (`...`) for metadata:
   - `type=string`
   - `description=...`
   - `pattern=\w*`
   - `example=...`
   - `default=...`
4. Returns list of variable objects

**Example input** (from Robot file):
```robot
${COSMOSDB_ENDPOINT}=    RW.Core.Import User Variable
...    COSMOSDB_ENDPOINT
...    type=string
...    description=The Cosmos DB account endpoint URL
...    pattern=\w*
...    example=https://myaccount.documents.azure.com:443/
```

**Example output:**
```json
{
  "name": "COSMOSDB_ENDPOINT",
  "type": "string",
  "description": "The Cosmos DB account endpoint URL",
  "pattern": "\\w*",
  "example": "https://myaccount.documents.azure.com:443/",
  "default": null
}
```

### 3. Frontend Display

Updated `frontend/src/pages/CodeBundleDetail.tsx`:

**Configuration Tab** now displays:
- Header: "Required User Variables" with count badge
- Card for each variable showing:
  - Variable name (in monospace, highlighted)
  - Type badge (string, integer, etc.)
  - Description (main explanation)
  - Example value (in highlighted code block)
  - Default value (if specified)
  - Pattern (validation regex, if specified)

**Visual Design:**
- Clean card-based layout
- Color-coded type chips
- Highlighted example values in success color
- Fallback message when no variables are found

### 4. TypeScript Interface

Added to `frontend/src/services/api.ts`:

```typescript
export interface CodeBundle {
  // ... existing fields ...
  user_variables?: Array<{
    name: string;
    type: string;
    description: string;
    pattern?: string;
    example?: string;
    default?: string | null;
  }>;
}
```

## 🔄 Data Flow

```
Robot File (*.robot)
    ↓
parse_robot_file_content()
    ↓
parse_user_variables()  ← NEW FUNCTION
    ↓
Codebundle model (user_variables field)
    ↓
PostgreSQL database
    ↓
API response (/api/v1/codebundles/{slug})
    ↓
Frontend CodeBundleDetail component
    ↓
User sees Configuration Variables & Templates tab
```

## 🚀 How to Use

### For Users (Browsing)

1. Navigate to any codebundle detail page
2. Click the **"Configuration"** tab
3. Scroll to **"Required User Variables"** section
4. View all variables with:
   - Name and type
   - Description
   - Example values
   - Default values (if any)

### For Admins (Re-parsing)

To populate `user_variables` for existing codebundles:

1. **Via Admin Panel:**
   - Go to **Admin Panel** → **Schedules**
   - Find `sync-parse-enhance-workflow`
   - Click **"Run Now"**

2. **Via API:**
   ```bash
   curl -X POST http://localhost:8001/api/v1/admin/trigger-workflow \
     -H "Authorization: Bearer $TOKEN"
   ```

3. **Automatic:**
   - Daily workflow runs automatically
   - New codebundles are parsed on sync

## 📊 Example Codebundles with User Variables

Codebundles that use `RW.Core.Import User Variable`:

- **azure-cosmosdb-query** - 9 variables (COSMOSDB_ENDPOINT, DATABASE_NAME, etc.)
- **curl-cmd** - Custom curl command variables
- **k8s-kubectl-cmd** - Kubernetes context and namespace variables
- Most **generic codebundles** that need user configuration

## 🧪 Testing

### Manual Test

1. Navigate to a codebundle that uses user variables:
   ```
   http://localhost:3000/collections/rw-generic-codecollection/codebundles/azure-cosmosdb-query
   ```

2. Click **"Configuration"** tab

3. Verify you see:
   - "Required User Variables" section
   - List of variables with descriptions
   - Example values
   - Type badges

### Database Query

Check if variables are populated:

```sql
SELECT 
  slug,
  jsonb_array_length(user_variables) as var_count,
  user_variables->0->>'name' as first_var
FROM codebundles 
WHERE jsonb_array_length(user_variables) > 0
LIMIT 10;
```

### API Test

```bash
curl http://localhost:8001/api/v1/codebundles/rw-generic-codecollection/azure-cosmosdb-query | jq '.user_variables'
```

Expected response:
```json
[
  {
    "name": "COSMOSDB_ENDPOINT",
    "type": "string",
    "description": "The Cosmos DB account endpoint URL",
    "example": "https://myaccount.documents.azure.com:443/",
    ...
  },
  ...
]
```

## 🐛 Troubleshooting

### Variables not showing up

**Cause:** Codebundles haven't been re-parsed since feature was added

**Fix:** Trigger sync/parse workflow:
```bash
# Via Admin Panel
Admin Panel → Schedules → sync-parse-enhance-workflow → "Run Now"

# Via API
POST /api/v1/admin/trigger-workflow
```

### Parser not extracting all variables

**Cause:** Variable declaration format doesn't match expected pattern

**Expected format:**
```robot
${VAR_NAME}=    RW.Core.Import User Variable
...    VAR_NAME
...    type=string
...    description=...
...    example=...
```

**Check:**
- Variable assignment must use `${VAR_NAME}=`
- Continuation lines must start with `...`
- Metadata must use `key=value` format

### Frontend not displaying variables

**Cause:** TypeScript interface mismatch or API not returning data

**Fix:**
1. Check API response includes `user_variables` field
2. Verify frontend TypeScript interface matches
3. Check browser console for errors
4. Restart frontend if needed: `docker-compose restart frontend`

## 📝 Future Enhancements

Potential improvements:

1. **Validation:** 
   - Frontend form validation using `pattern` field
   - Type-specific input components (string vs integer)

2. **Configuration Builder:**
   - Auto-generate YAML config from variables
   - Fill in examples as defaults
   - Export to workspace configuration

3. **Search:**
   - Filter codebundles by required variables
   - "Show me all codebundles that need AWS credentials"

4. **Documentation Links:**
   - Link variable names to documentation
   - Show which tasks use which variables

5. **Defaults Management:**
   - Organization-level defaults
   - Per-user variable overrides

## 🔗 Related Files

**Backend:**
- `backend/app/models/codebundle.py` - Database model
- `backend/app/tasks/fixed_parser.py` - Parser function
- `database/migrations/005_add_user_variables.sql` - Migration

**Frontend:**
- `frontend/src/pages/CodeBundleDetail.tsx` - UI component
- `frontend/src/services/api.ts` - TypeScript interface

**Documentation:**
- `docs/MCP_WORKFLOW.md` - Overall parsing workflow
- `docs/USER_VARIABLES_FEATURE.md` - This document

---

**Implemented:** 2026-01-24  
**Status:** ✅ Complete and ready for use
