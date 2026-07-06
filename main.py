#!/usr/bin/env python3
"""CLI entry point for TDMS to Excel converter."""

import argparse
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.converter import convert_tdms_to_excel
from src.gui.multi_source_app import run_gui


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert TDMS files to Excel format or launch the TDMS GUI browser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py test_data/Test_17_06_2026_05_46_54.tdms
  python main.py test_data/Test_17_06_2026_05_46_54.tdms -o output/converted.xlsx
  python main.py test_data/Test_17_06_2026_05_46_54.tdms -v
  python main.py --gui
  python main.py --gui test_data/Test_17_06_2026_05_46_54.tdms
        """
    )

    parser.add_argument(
        '--gui',
        action='store_true',
        help='Launch the Qt-based TDMS browser instead of converting to Excel'
    )
    
    parser.add_argument(
        'tdms_file',
        nargs='?',
        default=None,
        help='Path to input TDMS file'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='excel_file',
        default=None,
        help='Path to output Excel file (default: output/<filename>.xlsx)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Print progress information'
    )
    
    args = parser.parse_args()

    if args.gui:
        return run_gui(args.tdms_file)

    if not args.tdms_file:
        parser.error('tdms_file is required unless --gui is used')
    
    try:
        output_path = convert_tdms_to_excel(
            tdms_path=args.tdms_file,
            excel_path=args.excel_file,
            verbose=args.verbose
        )
        
        print(f"\nSuccess! Excel file created at: {output_path}")
        return 0
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
