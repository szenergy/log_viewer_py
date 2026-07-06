"""Main converter module for TDMS to Excel conversion."""

import os
import sys
from typing import Optional
from src.tdms_reader import read_tdms_file, get_groups, extract_group_data
from src.excel_writer import create_workbook, add_data_sheet, save_workbook


def print_progress(current: int, total: int, prefix: str = "", suffix: str = "") -> None:
    """
    Print a progress bar to stdout.
    
    Args:
        current: Current progress value
        total: Total progress value
        prefix: Prefix text
        suffix: Suffix text
    """
    if total == 0:
        return
    
    percent = current / total
    bar_length = 30
    filled = int(bar_length * percent)
    bar = '█' * filled + '░' * (bar_length - filled)
    
    status = f"{percent*100:.0f}%"
    output = f"\r{prefix} [{bar}] {status} {suffix}"
    
    # Use sys.stdout.write and flush for better control
    sys.stdout.write(output)
    sys.stdout.flush()
    
    # Print newline when complete
    if current >= total:
        print()


def convert_tdms_to_excel(tdms_path: str, excel_path: Optional[str] = None, verbose: bool = False) -> str:
    """
    Convert TDMS file to Excel format.
    
    Args:
        tdms_path: Path to input TDMS file
        excel_path: Path to output Excel file. If None, creates output in 'output/' directory
        verbose: Print progress information
        
    Returns:
        Path to the created Excel file
        
    Raises:
        FileNotFoundError: If TDMS file not found
        Exception: If conversion fails
    """
    # Validate input
    if not os.path.exists(tdms_path):
        raise FileNotFoundError(f"TDMS file not found: {tdms_path}")
    
    # Generate output path if not provided
    if excel_path is None:
        os.makedirs('output', exist_ok=True)
        base_name = os.path.splitext(os.path.basename(tdms_path))[0]
        excel_path = os.path.join('output', f"{base_name}.xlsx")
    
    if verbose:
        print(f"Reading TDMS file: {tdms_path}")
    
    # Read TDMS file
    tdms_file = read_tdms_file(tdms_path)
    
    # Get all groups
    groups = get_groups(tdms_file)
    
    if verbose:
        print(f"Found {len(groups)} group(s): {groups}")
    
    # Create workbook
    workbook = create_workbook()
    
    # Add each group as a sheet
    for idx, group_name in enumerate(groups, 1):
        if verbose:
            print(f"Processing group {idx}/{len(groups)}: {group_name}")
        
        # Extract group data with progress
        if verbose:
            print_progress(0, 1, prefix="  Extracting data...", suffix="")
        
        group_data = extract_group_data(tdms_file, group_name)
        
        if verbose:
            print_progress(1, 1, prefix="  Extracting data...", suffix="")
        
        # Create sheet name (handle special characters)
        sheet_name = group_name[:31] if group_name else "Data"  # Excel sheet name limit
        
        # Add to workbook with progress
        if verbose:
            print(f"  Writing to Excel sheet...")
        
        add_data_sheet(workbook, sheet_name, group_data, show_progress=verbose)
        
        if verbose:
            print(f"  Sheet '{sheet_name}' completed ({group_data.shape[0]} rows, {group_data.shape[1]} columns)")
    
    # Save workbook
    if verbose:
        print(f"Saving Excel file: {excel_path}")
    
    save_workbook(workbook, excel_path)
    
    if verbose:
        print("Conversion completed successfully!")
    
    return excel_path
