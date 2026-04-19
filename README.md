# finance-tui

A terminal dashboard for personal finance tracking, built with [Textual](https://textual.textualize.io/). Reads and writes transactions from markdown files, providing a keyboard-driven interface with KPIs, charts, anomaly detection, and full inline editing. Works with any local directory — optionally synced via iCloud, Obsidian, or any cloud provider.

```
 ▄█▄ ▄▀▄ ▄▄▀
 █ █ █ █ █
 ▀ ▀ ▀ ▀ ▀▀▀
```

## Features

### Home Dashboard

- **KPI row** — Balance (with YoY%), MoM growth, transaction count, last transaction date, active period
- **Account balances** — Proportional bars per account with balance and transaction count
- **Spending heatmap** — 12-month x 14-bucket intensity grid (GitHub-contributions style)
- **Balance evolution chart** — Braille-character line chart with green/red gradient segments per trend direction; navigable by all-time, year, or month granularity
- **Expense & income category breakdowns** — Horizontal bar panels with 5-shade color scales
- **Months over budget** — Per-category budget tracking showing how many months exceeded the threshold
- **Alerts panel** — Statistical outlier detection (z-score > 2.5) and duplicate transaction detection (same date/amount/account + 80% description similarity)
- **Tags & links panel** — Aggregate totals and counts for annotation metadata

### Transactions Table

- **10-column DataTable** — Status, ID, Date, Description, Amount, Category, Account, Running Sum, Tags, Links
- **Day-grouped rows** — Visual separators with daily sums
- **Pagination** — 50 rows per page with `n`/`p` navigation
- **Sorting** — By ID or date, ascending/descending
- **Inline editing** — Three-mode system: row cursor, cell cursor (enum cycling for category/account, day/month cycling for dates), and full text editing with cursor
- **Multi-select** — Space, Shift+arrows, Ctrl+A (page), Ctrl+Shift+A (global)
- **New transaction creation** — `l` key, with auto-defaults and immediate inline editing

### Filtering & Navigation

- **Command palette** (Ctrl+K) — Raycast-style overlay with prefix drill-down for search, category, account, tag, link, and period operations
- **Composable drill-down filters** — Click any overview panel row to filter; `x` to exclude. Multiple filters combine with AND logic
- **Interactive filter bar** — Keyboard-navigable chips showing active filters; delete or toggle include/exclude
- **Period selector** — All time / Year / Month with bracket-key navigation
- **Search query language** — `cat:Food`, `acc:Revolut`, `tag:grocery`, `link:Budget`, `person:Mom`, `>100`, `<-50`, or free text

### Bulk Operations

- **Validate/unvalidate** — Toggle checkbox on selected transactions (`v`)
- **Category change** — Via command palette with `cat:` prefix on selection
- **Tag add/remove** — Via command palette with `tag:` prefix on selection
- **Link add/remove** — Via command palette with `link:` prefix on selection

### AI Integration (Optional)

Requires either a local [Ollama](https://ollama.com/) instance or an `ANTHROPIC_API_KEY`. Gracefully disabled when neither is available.

- **Anomaly detection** — Outlier and duplicate alerts surfaced in the alerts panel (statistical, no API needed)
- **Auto-categorization** — Batch classification of transaction descriptions via Ollama (local) or Claude Haiku (cloud). Available in the import wizard and as a command palette action on filtered transactions with live progress feedback
- **Natural language queries** — Chat interface with 6 tool-use functions (spending totals, top expenses, category breakdowns, period comparisons, search, budget status)
- **Response caching** — SQLite-backed cache at `~/.finance-tui/cache.db`

### Live Reload

File watcher with 500ms debounce monitors the finance directory. Edits made in any external editor appear automatically. Self-writes are tracked to prevent reload loops.

## Data Format

Transactions are stored as Obsidian-flavored markdown checkbox lines:

```markdown
- [ ] `120.50` [[Food]] Grocery shopping ➕ 2024-03-15 [[Revolut_01]] 🆔 42 #weekly, [[Budget]]
- [x] `-45.00` [[Transport]] Metro pass ➕ 2024-03-14 [[CaixaBank_01]] 🆔 41
```

| Field | Format | Example |
|-------|--------|---------|
| Status | `[ ]` unvalidated / `[x]` validated | `- [x]` |
| Amount | Backtick-delimited decimal | `` `120.50` `` |
| Category | Wikilink | `[[Food]]` |
| Description | Free text | `Grocery shopping` |
| Date | ISO after ➕ emoji | `➕ 2024-03-15` |
| Account | Wikilink with suffix | `[[Revolut_01]]` |
| ID | After 🆔 emoji | `🆔 42` |
| Annotations | Optional: `#tag`, `[[link]]` comma-separated | `#weekly, [[Budget]]` |

### Directory Structure

```
04_finance/
├── Transactions/
│   ├── 2023.md          # One file per year
│   └── 2024.md
├── Categories/
│   ├── Food.md          # YAML frontmatter: budget, track
│   └── Transport.md
└── Accounts/
    ├── Revolut.md       # YAML frontmatter: aliases
    └── CaixaBank.md
```

## Keyboard Shortcuts

### Global

| Key | Action |
|-----|--------|
| `h` | Home tab |
| `t` | Transactions tab |
| `1`–`8` | Focus overview panel by number |
| `[` / `]` | Period backward / forward |
| `p` then `a`/`y`/`m` | Period mode: All / Year / Month |
| `v` | Toggle validation on selection |
| `c` | Category change dialog |
| `f` | Focus filter bar |
| `r` | Reload data from disk |
| `Escape` | Clear all filters |
| `Ctrl+K` | Command palette |
| `q` | Quit |

### Transaction Table

| Key | Action |
|-----|--------|
| `i` / `d` | Sort by ID / date (toggle direction) |
| `n` / `p` | Next / previous page |
| `N` / `P` | Last / first page |
| `l` | Log new transaction |
| `m` / `w` | Edit tags / links column |
| `Space` | Toggle row selection |
| `Shift+Up/Down` | Extend selection |
| `Ctrl+A` | Select all (page) |
| `Ctrl+Shift+A` | Select all (global) |
| `Enter` | Enter cell edit mode |
| `Escape` | Cancel edit / exit mode |

### Cell Edit Mode

| Key | Action |
|-----|--------|
| `Left` / `Right` | Navigate between columns |
| `Up` / `Down` | Cycle enum values or increment date |
| `Shift+Up/Down` | Increment date by month |
| `Enter` | Enter text editing or save |
| `Escape` | Cancel, restore original |

### Overview Panels

| Key | Action |
|-----|--------|
| `Enter` | Drill-down filter to this row |
| `x` | Exclusion filter (filter OUT this row) |

### Evolution Chart

| Key | Action |
|-----|--------|
| `a` / `y` / `m` | All / Year / Month scale |
| `f` | Toggle auto/fixed Y-axis |
| `Left` / `Right` | Navigate periods |
| `Enter` | Apply chart period to app |

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

```bash
# Clone the repository
git clone https://github.com/themanuem/finance-tui.git
cd finance-tui

# Install dependencies
uv sync

# Optional: Excel import support
uv sync --extra xlsx
```

### First Run

On first launch, the app shows an onboarding screen asking you to choose a finance data directory. This is where your transaction, category, and account files live (see [Data Format](#data-format)).

- **Existing data**: Point to a directory that already contains `Transactions/`, `Categories/`, and `Accounts/` subdirectories.
- **Starting fresh**: Enter any path — the app will create the subdirectories for you.

The chosen path is saved to `~/.finance-tui/config.json` and remembered across sessions.

### Optional: AI Features

For LLM-powered auto-categorization and natural language queries:

```bash
# Cloud (Anthropic)
export ANTHROPIC_API_KEY="sk-ant-..."

# Local (Ollama — no API key needed, just have Ollama running)
# The app auto-detects Ollama at localhost:11434
```

### Run

```bash
uv run fnc
# or
uv run finance-tui

# Import transactions from a file
uv run fnc import export.csv --account MyBank_01
```

## Architecture

```
src/finance_tui/
├── __main__.py          # Entry point
├── app.py               # Main Textual app, event handling, data flow
├── models.py            # Transaction, Account, Category dataclasses
├── config.py            # Paths, currency, constants
├── store.py             # FinanceStore — pandas DataFrame backend
├── parser.py            # Obsidian markdown → data models
├── writer.py            # Data models → markdown (round-trip safe)
├── watcher.py           # Debounced file system watcher
├── analytics.py         # Financial metrics and aggregations
├── commands.py          # Command palette provider
├── ai/
│   ├── cache.py         # SQLite response cache
│   ├── categorizer.py   # LLM auto-categorization (Ollama / Anthropic)
│   ├── insights.py      # Outlier & duplicate detection
│   └── nlq.py           # Natural language queries with tool use
├── importers/
│   ├── readers.py       # Multi-format file readers (.csv/.json/.xlsx/.md)
│   ├── mapper.py        # Heuristic column autodetection
│   ├── llm.py           # Unified LLM abstraction (Ollama + Anthropic)
│   └── transformer.py   # DataFrame → Transaction conversion
├── screens/
│   ├── overview.py      # Home dashboard layout
│   ├── transactions.py  # Transaction table pane
│   ├── dialogs.py       # Category change modal
│   ├── import_wizard.py # 3-step import modal with file browser
│   ├── file_browser.py  # File explorer dialog
│   ├── category_editor.py # Category management dialogs
│   └── insights.py      # NLQ chat interface
├── widgets/
│   ├── transaction_table.py  # DataTable with inline editing
│   ├── evolution_chart.py    # Balance line chart
│   ├── heatmap.py            # Spending heatmap
│   ├── donut_chart.py        # Category bar panels
│   ├── budget_bar.py         # Budget tracking
│   ├── account_table.py      # Account balances
│   ├── alerts_panel.py       # Anomaly alerts
│   ├── annotations_panel.py  # Tags & links
│   ├── filter_bar.py         # Active filter chips
│   ├── period_selector.py    # Period picker
│   ├── command_palette.py    # Prefix drill-down palette
│   ├── panel_table.py        # Base panel class
│   ├── kpi_card.py           # KPI display
│   ├── search_bar.py         # Query tokenizer
│   ├── histogram.py          # Amount histogram
│   └── scroll_arrows.py      # Drill-down messages
└── styles/
    └── app.tcss              # Textual CSS theme
```

### Data Flow

```
Obsidian Markdown Files
        │
        ▼
   parser.py ──────► models.py (Transaction, Account, Category)
        │
        ▼
    store.py ──────► pandas DataFrame (+ derived columns)
        │
        ▼
  analytics.py ────► KPIs, aggregations, budget comparisons
        │
        ▼
    app.py ─────────► Filtering pipeline (period → drilldown → search)
        │
        ▼
   widgets/* ──────► Rendered TUI components
        │
        ▼
   writer.py ◄─────── Inline edits written back to markdown
```

### Key Patterns

- **Message-driven**: Widgets post Textual `Message` subclasses upward; the app handles them centrally
- **Write-then-ignore**: Before disk writes, `watcher.ignore_next_change(path)` prevents redundant reloads
- **Three-mode editing**: Row cursor → cell cursor → text input, with per-column behavior (enum cycling, date cycling, free text)
- **Panel drill-down**: All overview panels share a `PanelTable` base class with consistent Enter/x filter behavior

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run with Textual dev tools
uv run textual run --dev src/finance_tui/app.py
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| TUI framework | [Textual](https://textual.textualize.io/) |
| Data processing | pandas + numpy |
| Charts | [textual-plotext](https://github.com/Textualize/textual-plotext) |
| Markdown parsing | Custom regex + PyYAML |
| File watching | watchdog |
| AI features | Ollama (local) / Anthropic SDK (cloud) |
| Build system | hatchling |
| Package manager | uv |

## License

MIT
