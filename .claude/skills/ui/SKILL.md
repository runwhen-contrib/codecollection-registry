---
name: runwhen-ui
description: Use when creating or modifying any UI component, page, or styling in user-pages. Enforces RunWhen's MUI++ design system standards.
---

# RunWhen UI Design System (MUI++)

This skill enforces RunWhen's UI standards when working on frontend code in `user-pages/`.

**ALWAYS apply these standards when:**
- Creating new pages or components
- Modifying existing UI code
- Reviewing UI-related pull requests
- Adding styles, colors, or typography

## Core Philosophy

RunWhen UI follows **"Stripe structure + Linear lightness"**:
- **Structured**: Clear visual hierarchy, visible borders, organized layouts
- **Light**: Font-weight 400, softer colors, generous whitespace
- **Consistent**: All values from design tokens, no magic numbers

### Brand Color Usage

**Primary blue (`#0570de`) is reserved for interactive elements only:**

| Use Blue For | DON'T Use Blue For |
|--------------|-------------------|
| Buttons (CTAs) | Page titles |
| Links | Section headers |
| Active tab indicator | Labels |
| Active filter chips | Decorative elements |
| Focus rings | |

**Page titles and headers use neutral dark gray (`text.primary`)** - this maintains visual hierarchy where blue draws attention to actions, not static text.

---

## 1. Design Tokens

### Typography

| Token | Value | Usage |
|-------|-------|-------|
| `fontSize.xs` | `12px` | Captions, badges, metadata |
| `fontSize.sm` | `13px` | Secondary text, table cells |
| `fontSize.base` | `14px` | Body text, form inputs |
| `fontSize.lg` | `15px` | Subheadings |
| `fontSize.xl` | `16px` | Page titles |
| `fontSize.2xl` | `18px` | Hero text (rare) |

| Token | Value | Usage |
|-------|-------|-------|
| `fontWeight.normal` | `400` | Body text (DEFAULT - keeps it light) |
| `fontWeight.medium` | `500` | Emphasis, selected states |
| `fontWeight.semibold` | `600` | Buttons, headings |

| Token | Value | Usage |
|-------|-------|-------|
| `lineHeight.tight` | `1.3` | Headings |
| `lineHeight.normal` | `1.5` | Body text (DEFAULT) |
| `lineHeight.relaxed` | `1.6` | Long-form content |

**NEVER use:**
- Font sizes below 12px (accessibility)
- Font sizes like 11px, 8px, 18px for body text
- `fontFamily: 'Inconsolata'` for inputs (use Inter)
- `!important` on font properties

### Colors

**Text Colors (softer, not harsh black):**

| Token | Value | Usage |
|-------|-------|-------|
| `colors.text.primary` | `#374151` | Main text |
| `colors.text.secondary` | `#6b7280` | Secondary/muted text |
| `colors.text.tertiary` | `#9ca3af` | Placeholders, disabled |
| `colors.text.muted` | `#d1d5db` | Very subtle text |

**Brand Colors:**

| Token | Value | Usage |
|-------|-------|-------|
| `colors.primary` | `#0570de` | Primary actions, links |
| `colors.primary.hover` | `#0559b3` | Hover state |
| `colors.primary.light` | `#e0f2fe` | Active chip background |

**Background Colors:**

| Token | Value | Usage |
|-------|-------|-------|
| `colors.bg.page` | `#ffffff` | Page background |
| `colors.bg.subtle` | `#f9fafb` | Cards, sidebar, group rows |
| `colors.bg.hover` | `#f3f4f6` | Hover states |
| `colors.bg.active` | `#e5e7eb` | Active/pressed states |

**Border Colors:**

| Token | Value | Usage |
|-------|-------|-------|
| `colors.border.light` | `#f3f4f6` | Subtle separators |
| `colors.border.default` | `#e5e7eb` | Standard borders |
| `colors.border.strong` | `#d1d5db` | Emphasized borders |

**NEVER use:**
- Hardcoded hex colors like `#D6D6D6`, `#797979`
- `rgba(0, 0, 0, 0.04)` - use token equivalents
- Pure black `#000000` for text
- MUI palette references like `neutral.darker` (migrate to tokens)

### Spacing

| Token | Value |
|-------|-------|
| `spacing.1` | `4px` |
| `spacing.2` | `8px` |
| `spacing.3` | `12px` |
| `spacing.4` | `16px` |
| `spacing.5` | `20px` |
| `spacing.6` | `24px` |
| `spacing.8` | `32px` |
| `spacing.10` | `40px` |

### Component Sizes

| Token | Value | Notes |
|-------|-------|-------|
| `sizes.rowHeight` | `44px` | Standard list row |
| `sizes.rowHeightCompact` | `40px` | Task rows, dense lists |
| `sizes.chipHeight` | `26px` | Filter chips, badges |
| `sizes.searchHeight` | `38px` | Search input |
| `sizes.buttonHeight` | `36px` | Standard buttons |

**NEVER use:**
- Row heights of 32px or 36px (too cramped)
- Chip heights of 16px (too small, accessibility issue)
- Chip font sizes of 8px (unreadable)

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `radius.sm` | `4px` | Small elements, badges |
| `radius.md` | `6px` | Buttons, inputs, chips (DEFAULT) |
| `radius.lg` | `8px` | Cards, modals |
| `radius.full` | `9999px` | Avatars only |

**NEVER use:**
- `borderRadius: 100px` for search bars (use `radius.md`)
- Inconsistent radius values across similar components

---

## 2. Page Structure Template

All pages MUST follow this structure (from concept diagram):

```
┌─────────────────────────────────────────────────────────────┐
│ Page Title | Workspace Name (dropdown)          [Row 1]     │
├─────────────────────────────────────────────────────────────┤
│ Tab1   Tab2   Tab3   Tab4                       [Row 2]     │
├─────────────────────────────────────────────────────────────┤
│ [🔍 Search bar]                    [Hero Button] [Row 3]    │
├─────────────────────────────────────────────────────────────┤
│ [Filter] [Filter] [Filter] [+Filters]           [Row 4]     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                    Content Area                  [Row 5]    │
│                                                             │
│              Formats: List | Form | Other                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Use `PageLayout` component:**

```tsx
<PageLayout
  title="Tasks"
  tabs={[
    { label: 'Tasks', value: 'tasks' },
    { label: 'Workflows', value: 'workflows' },
  ]}
  activeTab={activeTab}
  onTabChange={handleTabChange}
  searchPlaceholder="Search tasks..."
  onSearch={handleSearch}
  heroButton={{ label: 'Add Task', onClick: handleAdd }}
  filters={<FilterChips items={filters} />}
>
  {/* Content Area */}
  <DataList rows={rows} />
</PageLayout>
```

---

## 3. Component Standards

### PageHeader

```tsx
// CORRECT - neutral color, medium weight
<Typography
  sx={{
    fontWeight: tokens.fontWeight.medium,  // 500
    fontSize: tokens.fontSize.xl,          // 16px
    color: tokens.colors.text.primary,     // Dark gray
    letterSpacing: tokens.letterSpacing.tight,
  }}
>
  {pageTitle}
</Typography>

// WRONG - brand color for titles
<Typography
  sx={{
    fontWeight: 300,           // Too light
    fontSize: '18px',          // Hardcoded
    color: 'primary.main',     // Blue - reserve for CTAs
  }}
>
  {pageTitle}
</Typography>
```

**PageHeader specs:**
- Font size: 16px (`fontSize.xl`)
- Font weight: 500 (medium) - provides hierarchy
- Color: `text.primary` (dark gray) - NOT blue
- Letter spacing: tight (-0.01em)
- Border bottom: 1px solid `border.light`

### Tabs (MinimalTabs)

```tsx
// Tab label styling
<Typography
  sx={{
    fontSize: tokens.fontSize.sm,           // 13px
    fontWeight: isActive
      ? tokens.fontWeight.medium            // 500 when active
      : tokens.fontWeight.normal,           // 400 when inactive
    color: isActive
      ? tokens.colors.text.primary          // Dark when active
      : tokens.colors.text.secondary,       // Muted when inactive
  }}
>
  {tab.label}
</Typography>
```

**Tab specs:**
- Font size: 13px
- Inactive: weight 400, `text.secondary` color
- Active: weight 500, `text.primary` color
- Active indicator: 2px, `primary.main` color
- Container border: 1px solid `border.light`

### SearchBar

```tsx
// CORRECT
<SearchBar
  placeholder="Search tasks..."
  onSearch={handleSearch}
/>

// WRONG - don't build custom search inputs
<TextField
  sx={{
    '& .MuiInputBase-input': {
      fontFamily: 'Inconsolata',  // NO
      fontSize: '18px !important', // NO
    },
    borderRadius: '100px', // NO - not pill shape
  }}
/>
```

**SearchBar specs:**
- Height: 38px
- Border radius: 6px (not pill)
- Font: Inter, 14px, weight 400
- Border: 1px solid `colors.border.default`
- Focus: blue ring with `colors.primary`

### FilterChips

```tsx
// CORRECT
<FilterChip
  label="Kubernetes"
  icon={<KubernetesIcon />}
  active={isActive}
  onClick={handleClick}
/>

// WRONG
<Chip
  sx={{
    height: '16px',    // NO - too small
    fontSize: '8px',   // NO - unreadable
  }}
/>
```

**FilterChip specs:**
- Height: 26px
- Font: 13px, weight 400 (500 when active)
- Padding: 0 12px
- Border radius: 6px
- Active: `colors.primary.light` background, `colors.primary` text

### Buttons

```tsx
// CORRECT - Hero button (primary action)
<ActionButton variant="primary" onClick={handleAdd}>
  Add Task
</ActionButton>

// CORRECT - Secondary button
<ActionButton variant="secondary" onClick={handleCancel}>
  Cancel
</ActionButton>
```

**Button specs:**
- Height: 36px
- Font: 14px, weight 500
- Border radius: 6px
- No uppercase text (`textTransform: 'none'`)
- Primary: `colors.primary` background, white text
- Secondary: `colors.primary` border, `colors.primary` text, transparent background
  - Hover: `colors.primary.light` background, `colors.primary.hover` border/text

**When to use each variant:**
- **Primary**: Main action on the page (Add Task, Save, Submit)
- **Secondary**: Supporting actions (Run, Cancel, Export) - uses blue outline to maintain brand consistency while being visually lighter than primary

### DataList / Tree Rows

**Row heights:**
- Group rows: 40px, background `colors.bg.subtle`
- SLX rows: 44px
- Task rows: 40px

**Row borders:**
- Use 1px solid `colors.border.light`
- NOT `0.05px` or `0.5px` (inconsistent rendering)

**Hover actions:**
- Show on row hover
- Icon buttons: 28px × 28px
- Icon size: 16px

### Badges/Labels

```tsx
// CORRECT
<Badge variant="subtle">SLX</Badge>

// WRONG
<Chip
  sx={{
    height: '16px',
    fontSize: '8px',
    borderWidth: '0.5px', // NO
  }}
/>
```

**Badge specs:**
- Height: 20px
- Font: 12px, weight 400
- Padding: 0 8px
- Border radius: 4px
- Background: `colors.bg.subtle`
- Border: 1px solid `colors.border.light`

---

## 4. Verification Workflow

**CRITICAL: Code written ≠ task complete. Visual verification is required.**

### After Creating/Modifying Each Component

1. **Ask user to verify rendered output**
   ```
   "I've implemented the SearchBar component. Can you check localhost:3002
   and confirm it matches the mockup? Specifically verify:
   - Border is visible (not just an underline)
   - Height is 38px
   - Border radius is 6px (not pill-shaped)"
   ```

2. **Wait for user confirmation before proceeding**
   - Do NOT assume code is correct without visual verification
   - If user reports differences, fix before moving on

3. **Request screenshot if needed**
   - "Can you share a screenshot so I can compare to the mockup?"

### Before Starting Component Work

1. **Check theme.ts for conflicting defaults**
   ```tsx
   // theme.ts may have defaults that override your component props
   // Example: MuiTextField defaultProps variant: 'standard'
   // This will override variant="outlined" unless you use themeOverrides
   ```

2. **Always set explicit props, don't rely on defaults**
   ```tsx
   // CORRECT - explicit variant
   <TextField variant="outlined" ... />

   // WRONG - relies on default which may be overridden
   <TextField ... />
   ```

3. **Check themeOverrides.ts for existing overrides**
   - Understand what's already configured
   - Add new overrides there, not inline in components

### Comparison Checklist

When comparing component to mockup, verify:
- [ ] Overall dimensions match (height, width)
- [ ] Border style matches (color, width, radius)
- [ ] Background color matches
- [ ] Typography matches (size, weight, color)
- [ ] Spacing matches (padding, margin)
- [ ] States match (hover, focus, active, disabled)

---

## 5. DataGrid / Tree Row Styling

### Row Type Styling

| Row Type | Height | Background | Label Style |
|----------|--------|------------|-------------|
| **Group row** | 40px | `colors.bg.subtle` | 12px, weight 500, `text.secondary`, UPPERCASE, letter-spacing wide |
| **SLX row** | 44px | transparent | 13px, weight 400, `text.primary` |
| **Task row** | 40px | transparent | 12px, weight 400, `text.secondary` |

### DataGrid Container

```tsx
sx={{
  border: `1px solid ${tokens.colors.border.light}`,
  borderRadius: `${tokens.radius.lg}px`,
  overflow: 'hidden',
}}
```

### Row Borders

```tsx
// CORRECT - use design tokens
borderBottom: `1px solid ${tokens.colors.border.light}`

// WRONG - inconsistent rendering, not from tokens
borderBottom: '0.05px solid rgba(0, 0, 0, 0.04)'
```

### Group Row Label

```tsx
<Typography
  sx={{
    fontSize: tokens.fontSize.xs,        // 12px
    fontWeight: tokens.fontWeight.medium, // 500
    color: tokens.colors.text.secondary,  // #6b7280
    textTransform: 'uppercase',
    letterSpacing: tokens.letterSpacing.wide,
  }}
>
  {groupLabel}
</Typography>
```

### SLX Row Label

```tsx
<Typography
  sx={{
    fontSize: tokens.fontSize.sm,        // 13px
    fontWeight: tokens.fontWeight.normal, // 400
    color: tokens.colors.text.primary,    // #374151
  }}
>
  {slxName}
</Typography>
```

---

## 6. Enforcement Checklist

When reviewing or writing UI code, verify:

### Typography
- [ ] No font sizes below 12px
- [ ] No hardcoded font sizes (use tokens)
- [ ] Font weight 400 for body text, 500 for emphasis
- [ ] No `!important` on font properties
- [ ] No custom font families in inputs

### Colors
- [ ] No hardcoded hex colors
- [ ] No `rgba()` colors (use tokens)
- [ ] No palette colors (`neutral.dark`, etc.) - use tokens
- [ ] Text uses `colors.text.*` tokens
- [ ] Borders use `colors.border.*` tokens
- [ ] No pure black (`#000000`) for text
- [ ] Page titles use `text.primary`, NOT `primary.main` (blue)
- [ ] Brand color (blue) reserved for CTAs and interactive elements only

### Spacing & Sizing
- [ ] Row heights ≥ 40px
- [ ] Chip heights ≥ 24px
- [ ] Border radius from tokens (4px, 6px, 8px)
- [ ] No pill-shaped inputs (no `borderRadius: 100px`)
- [ ] Consistent padding using spacing tokens

### Components
- [ ] New pages use `PageLayout`
- [ ] Search uses `SearchBar` component
- [ ] Filters use `FilterChip` component
- [ ] No custom implementations of standard components

### Borders
- [ ] Border width is 1px (not 0.5px or 0.05px)
- [ ] Border colors from tokens
- [ ] Consistent border-radius

---

## 7. Migration Guide

When updating existing code:

### Before (Current Style)
```tsx
<Typography sx={{ fontSize: 11, color: 'text.secondary' }}>
  {taskName}
</Typography>

<Chip
  sx={{
    height: '16px',
    fontSize: '8px',
    borderWidth: '0.5px',
  }}
/>

<TextField
  sx={{
    '& .MuiInputBase-input': {
      fontFamily: 'Inconsolata',
      fontSize: '18px !important',
    },
    borderRadius: '100px',
  }}
/>
```

### After (MUI++ Style)
```tsx
<Typography
  sx={{
    fontSize: tokens.fontSize.sm,
    color: tokens.colors.text.secondary
  }}
>
  {taskName}
</Typography>

<FilterChip label="SLX" />

<SearchBar placeholder="Search tasks..." />
```

---

## 8. File Locations

```
user-pages/
├── styles/
│   ├── theme.ts              # Base MUI theme
│   ├── themeOverrides.ts     # MUI++ component overrides
│   └── designTokens.ts       # Token definitions
│
├── components/
│   ├── layouts/
│   │   └── PageLayout.tsx    # Standard page template
│   │
│   └── ui/                   # Standardized primitives
│       ├── SearchBar.tsx
│       ├── FilterChip.tsx
│       ├── ActionButton.tsx
│       ├── Badge.tsx
│       └── DataList.tsx
```

---

## 9. Component Reuse Pattern

**Components are created ONCE and imported everywhere.** Pages do NOT rewrite search bars, tabs, or layouts.

### How Pages Use Components

```tsx
// pages/workspace/[workspace]/tasks/[[...tab]].tsx

import { PageLayout } from '@/components/layouts/PageLayout'
import { SearchBar, FilterChips, ActionButton } from '@/components/ui'

function TasksPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeFilters, setActiveFilters] = useState<string[]>([])

  return (
    <PageLayout
      title="Tasks"
      tabs={TABS}
      activeTab={activeTab}
      onTabChange={handleTabChange}
    >
      {/* Row 3: Search + Hero Button */}
      <PageLayout.ActionBar>
        <SearchBar
          placeholder="Search tasks..."
          value={searchQuery}
          onChange={setSearchQuery}
        />
        <ActionButton onClick={handleAddTask}>
          Add Task
        </ActionButton>
      </PageLayout.ActionBar>

      {/* Row 4: Filters */}
      <PageLayout.Filters>
        <FilterChips
          items={platformFilters}
          active={activeFilters}
          onToggle={handleFilterToggle}
        />
      </PageLayout.Filters>

      {/* Row 5: Content - this is page-specific */}
      <PageLayout.Content>
        <DataGridPro {...dataGridProps} />
      </PageLayout.Content>
    </PageLayout>
  )
}
```

### What's Reusable vs Page-Specific

| Reusable (import from ui/) | Page-Specific (write in page) |
|---------------------------|------------------------------|
| `PageLayout` | Data fetching logic |
| `SearchBar` | DataGrid columns/rows |
| `FilterChips` | Business logic handlers |
| `ActionButton` | Page-specific dialogs |
| `Badge` | Custom visualizations |
| `DataList` (basic) | Complex data transformations |
| `MinimalTabs` | |

### Component API Consistency

All UI components follow consistent patterns:

```tsx
// All have similar prop structure
<SearchBar
  value={string}           // Controlled value
  onChange={(val) => void} // Change handler
  placeholder={string}     // Optional placeholder
  disabled={boolean}       // Optional disabled state
/>

<FilterChips
  items={Array}            // Data
  active={Array}           // Selected items
  onToggle={(id) => void}  // Toggle handler
/>

<ActionButton
  variant="primary" | "secondary"
  onClick={() => void}
  loading={boolean}
  disabled={boolean}
>
  {children}
</ActionButton>
```

---

## 10. Common Pitfalls

### 1. Theme defaults override component props

```tsx
// theme.ts has: MuiTextField: { defaultProps: { variant: 'standard' } }

// This renders as 'standard' (underline only), NOT outlined:
<TextField variant="outlined" />  // prop is ignored!

// FIX: Override in themeOverrides.ts
MuiTextField: {
  defaultProps: { variant: 'outlined' }
}
```

### 2. Badge variants don't match mockup

```tsx
// Mockup shows: background + border together
// Original Badge had:
//   - subtle: background only
//   - outlined: border only, transparent bg

// FIX: Both variants should have background + border
...(variant === 'subtle' && {
  backgroundColor: colors.bg,
  border: `1px solid ${colors.border}`,  // Added
  color: colors.text,
}),
```

### 3. Not checking rendered output

```
// WRONG workflow:
1. Write component code
2. Assume it matches mockup
3. Move on  <-- BUG INTRODUCED HERE

// CORRECT workflow:
1. Write component code
2. Ask user to verify in browser
3. User confirms OR reports differences
4. Fix differences
5. Get confirmation
6. Move on
```

### 4. Using rgba() instead of tokens

```tsx
// WRONG
borderBottom: '0.05px solid rgba(0, 0, 0, 0.04)'

// CORRECT
borderBottom: `1px solid ${tokens.colors.border.light}`
```

### 5. Inconsistent row typography

```tsx
// Group rows, SLX rows, and task rows need DIFFERENT styles
// Don't copy-paste the same Typography sx across row types
// Refer to Section 5 for correct styles per row type
```

### 6. Using brand color for page titles

```tsx
// WRONG - blue title dilutes visual hierarchy
<Typography sx={{ color: 'primary.main' }}>
  Tasks
</Typography>

// CORRECT - neutral dark, reserve blue for CTAs
<Typography sx={{ color: tokens.colors.text.primary }}>
  Tasks
</Typography>
```

**Rule:** Blue = interactive. Titles = structural. Keep them separate.

### 7. Using palette colors instead of tokens

```tsx
// WRONG - palette colors not from design system
color: 'neutral.dark'
color: 'neutral.darkest'
borderColor: 'rgba(0, 0, 0, 0.08)'

// CORRECT - design tokens
color: tokens.colors.text.secondary
color: tokens.colors.text.primary
borderColor: tokens.colors.border.light
```

---

## 11. Reference: Mockup

Interactive mockup showing the design system:
`user-pages/mockups/tasks-page-stripe-style.html`

Open in browser to compare "Stripe Style (New)" vs "Current Style" and view token values.

---

## 12. Scrollable Tables

### DO NOT use DataGridPro for simple scrollable tables

DataGridPro has complex internal DOM with multiple nested scrollable containers (`.MuiDataGrid-main`, `.MuiDataGrid-virtualScroller`, etc.) that create **double scrollbar issues** that are extremely difficult to fix with CSS. Only use DataGridPro when you need its advanced features (tree data, checkbox selection, column sorting, virtual row rendering for 1000+ rows).

### Use Box-based tables for simple lists

For tables that just need a header row, clickable rows, and scroll — use the **UsersPanel pattern**: a plain Box with `overflowY: 'auto'` and `maxHeight`. This is simpler, more predictable, and guaranteed to produce a single scrollbar.

```tsx
// CORRECT — simple scrollable table (UsersPanel pattern)
<Box
  sx={{
    border: `1px solid ${tokens.colors.border.light}`,
    borderRadius: `${tokens.radius.lg}px`,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
  }}
>
  {/* Sticky header */}
  <Box
    sx={{
      display: 'flex',
      alignItems: 'center',
      px: 2,
      py: 1.5,
      backgroundColor: tokens.colors.bg.subtle,
      borderBottom: `1px solid ${tokens.colors.border.light}`,
      flexShrink: 0,
    }}
  >
    <Typography sx={{ flex: 3, fontSize: tokens.fontSize.xs, fontWeight: tokens.fontWeight.medium, color: tokens.colors.text.secondary, textTransform: 'uppercase', letterSpacing: tokens.letterSpacing.wide }}>
      Column 1
    </Typography>
    <Typography sx={{ flex: 2, /* same header styles */ }}>
      Column 2
    </Typography>
  </Box>

  {/* Scrollable body — single native scrollbar */}
  <Box
    sx={{
      maxHeight: 340,
      overflowY: 'auto',
      '&::-webkit-scrollbar': { width: '6px' },
      '&::-webkit-scrollbar-track': { background: 'transparent' },
      '&::-webkit-scrollbar-thumb': { background: '#c1c1c1', borderRadius: '3px' },
      '&::-webkit-scrollbar-thumb:hover': { background: '#a8a8a8' },
      scrollbarWidth: 'thin',
      scrollbarColor: '#c1c1c1 transparent',
    }}
  >
    {rows.map((row, idx) => (
      <Box
        key={row.id}
        onClick={() => onSelect(row)}
        sx={{
          display: 'flex',
          alignItems: 'center',
          px: 2,
          py: 1,
          minHeight: `${tokens.sizes.rowHeight}px`,
          borderBottom: idx < rows.length - 1 ? `1px solid ${tokens.colors.border.light}` : 'none',
          cursor: 'pointer',
          transition: `background-color ${tokens.transitions.fast}`,
          '&:hover': { backgroundColor: tokens.colors.bg.subtle },
        }}
      >
        <Typography sx={{ flex: 3 }}>{row.col1}</Typography>
        <Typography sx={{ flex: 2 }}>{row.col2}</Typography>
      </Box>
    ))}
  </Box>
</Box>

// WRONG — DataGridPro for a simple list (scrollbar nightmares)
<DataGridPro rows={rows} columns={columns} />
```

### When to use what

| Approach | Use When |
|----------|----------|
| **Box-based table** | Simple list with < 500 rows, clickable rows, no sorting/filtering by column |
| **MUI `<TableContainer>` + `<Table stickyHeader>`** | Need standard HTML table semantics, accessibility, or column alignment |
| **DataGridPro** | Tree data, checkbox selection, column sorting/resizing, virtual rendering for 1000+ rows |

### Scrollbar styling (for any scrollable container)

Always use this pattern to remove the grey scrollbar gutter:

```tsx
sx={{
  overflowY: 'auto',
  '&::-webkit-scrollbar': { width: '6px' },
  '&::-webkit-scrollbar-track': { background: 'transparent' },
  '&::-webkit-scrollbar-thumb': { background: '#c1c1c1', borderRadius: '3px' },
  '&::-webkit-scrollbar-thumb:hover': { background: '#a8a8a8' },
  scrollbarWidth: 'thin',
  scrollbarColor: '#c1c1c1 transparent',
}}
```

### DataGridPro scrollbar (when you must use it)

If DataGridPro is required, use the `'& *'` wildcard pattern to style all internal scrollbars uniformly. Do NOT try to hide/show scrollbars on specific internal containers — DataGridPro manages its own overflow via inline styles that override CSS.

```tsx
// CORRECT — style all scrollbars uniformly
<DataGridPro
  sx={{
    overflow: 'hidden',
    '& *': {
      '&::-webkit-scrollbar': { width: '6px' },
      '&::-webkit-scrollbar-track': { background: 'transparent' },
      '&::-webkit-scrollbar-thumb': { background: '#c1c1c1', borderRadius: '3px' },
      scrollbarWidth: 'thin',
      scrollbarColor: '#c1c1c1 transparent',
    },
  }}
/>

// WRONG — targeting individual internal containers
<DataGridPro
  sx={{
    '& .MuiDataGrid-main': { overflow: 'hidden !important' },           // Breaks scroll
    '& .MuiDataGrid-virtualScroller': { scrollbarWidth: 'thin' },       // Creates double scrollbar
  }}
/>
```

### Reference implementations

- **Box-based table**: `components/settings/UsersPanel.tsx`, `components/dialogs/add-slx-wizard/CodeBundleBrowser.tsx`
- **DataGridPro with scrollbar**: `pages/workspace/[workspace]/studio/[[...tab]].tsx` (Tasks tree)

---

*Last updated: 2026-02-09*
*Version: 1.3 - Added scrollable table guidelines, Box-based table pattern, scrollbar styling rules*
