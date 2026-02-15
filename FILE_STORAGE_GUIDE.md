# File Storage Guide - Integrated System

## Directory Structure

### After Integration

```
D:\E-BOOK\axdcdcpdf\
│
├── downloads_temp/              ← Temporary download folder (auto-cleaned)
│   ├── ti/                      ← Downloaded PDFs by vendor
│   ├── st/
│   ├── analog/
│   └── ...
│
├── downloads_classified/        ← Final classified archive ⭐ MAIN OUTPUT
│   ├── TI/
│   │   ├── datasheet/
│   │   │   ├── power_ic/
│   │   │   │   ├── buck/
│   │   │   │   │   ├── TPS54620.pdf
│   │   │   │   │   └── LM5164.pdf
│   │   │   │   └── boost/
│   │   │   │       └── TPS61088.pdf
│   │   │   └── control_loop/
│   │   └── application_note/
│   │       └── power_ic/
│   │           └── buck/
│   ├── ST/
│   │   └── datasheet/
│   ├── Analog/
│   └── Unknown/
│       ├── LowConfidence/       ← Low confidence classifications
│       └── ErrorFiles/          ← Error files
│
├── downloads_continuous/        ← Original download folder (still available)
│   └── ...                      ← Can be classified using classify_existing.bat
│
├── metadata.jsonl              ← Classification metadata
├── classified_files.db         ← Classification database
└── integrated_system.log       ← System log
```

## File Flow

```
┌─────────────────┐
│  Gemini         │
│  Generate       │ 
│  Keywords       │
└────────┬────────┘
         ↓
┌─────────────────┐
│  Google         │
│  Search         │
└────────┬────────┘
         ↓
┌─────────────────┐
│ downloads_temp/ │ ← 1. Files download here first
│ (Temporary)     │    (organized by vendor)
└────────┬────────┘
         ↓
    [Wait 15s]      ← File stabilization
         ↓
┌─────────────────┐
│  Classifier     │ ← 2. Analyze PDF content
│  4-Dimension    │    (vendor/type/topic/topology)
└────────┬────────┘
         ↓
┌─────────────────┐
│downloads_       │ ← 3. Move to classified structure
│classified/      │    ⭐ FINAL LOCATION
│(Permanent)      │
└─────────────────┘
```

## Main Output Directory

### ⭐ `downloads_classified/`

This is where ALL classified PDFs are stored permanently.

**Path Format:**
```
downloads_classified/{Vendor}/{DocType}/{Topic}/{Topology}/{filename}.pdf
```

**Example:**
```
downloads_classified/TI/datasheet/power_ic/buck/TPS54620.pdf
                     ↑   ↑         ↑        ↑    ↑
                   Vendor Type    Topic  Topology File
```

### Classification Dimensions

1. **Vendor** (厂商)
   - TI, ST, Analog, Infineon, Microchip, ROHM, NXP, MPS, etc.

2. **Doc Type** (文档类型) - Most Important!
   - `datasheet` - Product datasheets
   - `application_note` - Application notes
   - `reference_design` - Reference designs
   - `eval_user_guide` - Evaluation board guides
   - `whitepaper` - White papers
   - `standard` - Standards

3. **Topic** (主题)
   - `power_ic` - Power ICs
   - `power_stage` - Power stage components
   - `magnetics` - Magnetic components
   - `emi_emc` - EMI/EMC
   - `control_loop` - Control loops
   - `thermal` - Thermal management

4. **Topology** (拓扑)
   - `buck` - Step-down
   - `boost` - Step-up
   - `buck_boost` - Buck-boost
   - `flyback` - Flyback
   - `llc` - LLC resonant
   - `cllc` - CLLC bidirectional

## Temporary vs Permanent

| Folder | Purpose | Cleaned? | Final? |
|--------|---------|----------|--------|
| `downloads_temp/` | Download staging | ✅ Yes (after classification) | ❌ No |
| `downloads_classified/` | Classified archive | ❌ No | ✅ Yes ⭐ |
| `downloads_continuous/` | Old download folder | ❌ No | Optional |

## Configuration

In `integrated_config.json`:

```json
{
    "paths": {
        "download_dir": "./downloads_temp",        ← Temporary
        "classified_dir": "./downloads_classified" ← Permanent ⭐
    }
}
```

## Check Your Files

### View classified files:
```bash
# Windows
dir downloads_classified /s

# PowerShell
Get-ChildItem downloads_classified -Recurse

# Tree view
tree /F downloads_classified
```

### Count files by vendor:
```powershell
Get-ChildItem downloads_classified -Directory | ForEach-Object {
    $count = (Get-ChildItem $_.FullName -Recurse -Filter "*.pdf").Count
    "$($_.Name): $count files"
}
```

### Check metadata:
```bash
# View latest classifications
Get-Content metadata.jsonl -Tail 10

# Count total classified
(Get-Content metadata.jsonl).Count
```

## Output Files

### 1. metadata.jsonl
**Location:** `D:\E-BOOK\axdcdcpdf\metadata.jsonl`

Records classification details for each PDF:
```json
{
  "doc_id": "7f3a8bc...",
  "dst_path": "downloads_classified/TI/datasheet/power_ic/buck/TPS54620.pdf",
  "vendor": "TI",
  "doc_type": "datasheet",
  "confidence": 0.89
}
```

### 2. classified_files.db
**Location:** `D:\E-BOOK\axdcdcpdf\classified_files.db`

SQLite database preventing duplicate processing.

### 3. integrated_system.log
**Location:** `D:\E-BOOK\axdcdcpdf\integrated_system.log`

System operation log.

## Quick Commands

### Where are my files?
```bash
cd downloads_classified
dir /s *.pdf
```

### How many files classified?
```bash
dir downloads_classified\*.pdf /s | find /c ".pdf"
```

### Find specific vendor:
```bash
dir downloads_classified\TI\*.pdf /s
```

### Find specific document type:
```bash
dir downloads_classified\*\datasheet\*.pdf /s
```

## Important Notes

⚠️ **DO NOT manually edit `downloads_temp/`**
- This folder is automatically managed
- Files are moved after classification

✅ **Safe to browse `downloads_classified/`**
- This is your permanent archive
- Organized and searchable structure

📋 **Use metadata.jsonl for analysis**
- Import to database
- Generate statistics
- Build search index

---

**Summary:** Your files end up in `downloads_classified/` with a 4-level organized structure!
