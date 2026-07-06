# TDMS to Excel Converter - Implementation Plan

## Project Overview

Create a Python-based converter to read TDMS (TDM Streaming) files and export their data to Excel format.

**Test Data**: `test_data/Test_17_06_2026_05_46_54.tdms`

---

## Phase 1: Project Setup

### 1.1 Directory Structure

```
test_data_interpreter/
├── src/
│   ├── __init__.py
│   ├── tdms_reader.py          # TDMS file reading logic
│   ├── excel_writer.py         # Excel export logic
│   └── converter.py            # Main conversion orchestrator
├── tests/
│   ├── __init__.py
│   └── test_converter.py       # Unit tests
├── test_data/
│   └── Test_17_06_2026_05_46_54.tdms
├── output/                     # Generated Excel files (gitignore)
├── requirements.txt            # Python dependencies
├── main.py                     # CLI entry point
└── README.md                   # Documentation
```

### 1.2 Dependencies

- **npTDMS** (~0.30.0): Read TDMS files
- **pandas** (~2.0.0): Data manipulation and analysis
- **openpyxl** (~3.10.0): Excel file creation and styling

---

## Phase 2: Exploration & Analysis

### 2.1 Understand TDMS File Structure

- [ ] Inspect test TDMS file to identify:
  - Number of groups and channels
  - Data types and sizes
  - Metadata (units, descriptions, timestamps)
  - Data organization and hierarchy

### 2.2 Define Conversion Strategy

- [ ] Determine Excel sheet organization:
  - One sheet per group or one sheet per channel?
  - How to handle large datasets (65K row limit consideration)?
  - Metadata placement (separate sheet or column headers)?

---

## Phase 3: Core Implementation

### 3.1 TDMS Reader Module (`src/tdms_reader.py`)

**Responsibilities:**

- Load TDMS file using npTDMS
- Extract groups, channels, and data
- Handle metadata (units, descriptions)
- Support data filtering/selection

**Key Functions:**

```python
- read_tdms_file(filepath) → TdmsFile
- get_groups(tdms_file) → List[str]
- get_channels(tdms_file, group) → List[str]
- extract_channel_data(tdms_file, group, channel) → DataFrame
- get_metadata(tdms_file) → Dict
```

### 3.2 Excel Writer Module (`src/excel_writer.py`)

**Responsibilities:**

- Create Excel workbook structure
- Write data to sheets
- Apply formatting (headers, freezing, column width)
- Handle large datasets

**Key Functions:**

```python
- create_workbook() → Workbook
- add_data_sheet(workbook, name, data) → None
- add_metadata_sheet(workbook, metadata) → None
- format_worksheet(worksheet) → None
- save_workbook(workbook, filepath) → None
```

### 3.3 Main Converter Module (`src/converter.py`)

**Responsibilities:**

- Orchestrate TDMS reading and Excel writing
- Handle configuration options
- Implement conversion logic

**Key Functions:**

```python
- convert_tdms_to_excel(tdms_path, excel_path, config) → None
- build_config(options) → Dict
```

### 3.4 CLI Entry Point (`main.py`)

Implement cli argument parsing with default python libraries.
The following options should be available:

---

## Phase 4: Features & Options

### 4.1 Basic Features (MVP)

- [ ] Read TDMS file
- [ ] Extract all groups and channels
- [ ] Write data to Excel (one group per sheet)
- [ ] Include column headers with channel names

### 4.2 Advanced Features

- [ ] Metadata sheet with file info and units
- [ ] Custom sheet naming and organization
- [ ] Data filtering/selection
- [ ] Timestamp formatting
- [ ] Column width auto-adjustment
- [ ] Header freezing
- [ ] Progress reporting for large files

### 4.3 Configuration Options

- [ ] Output format: single sheet vs. multiple sheets
- [ ] Include/exclude metadata
- [ ] Sheet naming convention
- [ ] Data slicing (e.g., first N rows/samples)

---

## Phase 5: Testing & Validation

### 5.1 Unit Tests (`tests/test_converter.py`)

- [ ] Test TDMS file reading
- [ ] Test data extraction
- [ ] Test Excel file creation
- [ ] Test round-trip validation (optional)

### 5.2 Integration Test with Real Data

- [ ] Convert test TDMS file
- [ ] Verify Excel output
- [ ] Validate data integrity
- [ ] Check formatting

### 5.3 Edge Cases

- [ ] Empty channels
- [ ] Large datasets
- [ ] Special characters in names
- [ ] Multiple data types

---

## Phase 6: Documentation & Packaging

### 6.1 README.md

- Installation instructions
- Usage examples
- Configuration options
- Troubleshooting

### 6.2 Code Documentation

- Docstrings for all functions
- Type hints throughout

### 6.3 Requirements Management

- Pin versions in `requirements.txt`
- Document compatibility notes

---

## Implementation Priority

### Iteration 1 (MVP)

1. Set up project structure
2. Install and test npTDMS with test data
3. Build basic TDMS reader
4. Build basic Excel writer
5. Create main converter
6. Test with provided TDMS file

### Iteration 2 (Enhanced)

1. Add metadata extraction and sheet
2. Improve formatting (headers, freezing)
3. Add CLI interface
4. Add error handling and logging

### Iteration 3 (Polish)

1. Add tests
2. Add configuration options
3. Documentation
4. Performance optimization for large files

---

## Success Criteria

- ✅ Can read the test TDMS file without errors
- ✅ Excel file is created with correct data
- ✅ Data types are preserved
- ✅ Column headers are clear and useful
- ✅ File is readable in Excel/LibreOffice
- ✅ CLI interface is user-friendly

---

## Technical Notes

### TDMS Format

- Proprietary binary format by National Instruments
- Hierarchical: File → Groups → Channels → Data
- Supports raw data and metadata

### Excel Considerations

- Row limit: 1,048,576 rows per sheet
- For large TDMS files, may need multiple sheets or compression
- Consider using `openpyxl` for advanced styling

### Python Version

- Target: Python 3.8+
- Use the virtual environment in `.venv`
