#!/usr/bin/env python3
"""Quick exploration script for TDMS file structure."""

from nptdms import TdmsFile

# Load test TDMS file
tdms_file = TdmsFile.read('test_data/Test_17_06_2026_05_46_54.tdms')

# Explore structure
print("Groups:", [group.name for group in tdms_file.groups()])

for group in tdms_file.groups():
    print(f"\nGroup: {group.name}")
    for channel in group.channels():
        print(f"  Channel: {channel.name}")
        print(f"    Attributes: {list(channel.properties.keys())}")
        print(f"    Data type: {type(channel.data)}")
        print(f"    Data shape: {channel.data.shape if hasattr(channel.data, 'shape') else len(channel.data)}")
        print(f"    First few values: {channel.data[:5] if len(channel.data) > 0 else 'empty'}")
