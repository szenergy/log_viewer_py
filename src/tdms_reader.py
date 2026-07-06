"""TDMS file reader module."""

from typing import List, Dict, Any
import pandas as pd
from nptdms import TdmsFile


def read_tdms_file(filepath: str) -> TdmsFile:
    """
    Load a TDMS file.
    
    Args:
        filepath: Path to the TDMS file
        
    Returns:
        TdmsFile object
    """
    return TdmsFile.read(filepath)


def get_groups(tdms_file: TdmsFile) -> List[str]:
    """
    Get all group names from TDMS file.
    
    Args:
        tdms_file: TdmsFile object
        
    Returns:
        List of group names
    """
    return [group.name for group in tdms_file.groups()]


def get_channels(tdms_file: TdmsFile, group_name: str) -> List[str]:
    """
    Get all channel names for a specific group.
    
    Args:
        tdms_file: TdmsFile object
        group_name: Name of the group
        
    Returns:
        List of channel names
    """
    group = tdms_file[group_name]
    return [channel.name for channel in group.channels()]


def extract_channel_data(tdms_file: TdmsFile, group_name: str, channel_name: str) -> pd.DataFrame:
    """
    Extract data from a specific channel as a DataFrame.
    
    Args:
        tdms_file: TdmsFile object
        group_name: Name of the group
        channel_name: Name of the channel
        
    Returns:
        DataFrame with channel data
    """
    channel = tdms_file[group_name][channel_name]
    data = channel.data
    
    # Create DataFrame with data
    df = pd.DataFrame({
        channel_name: data
    })
    
    return df


def extract_group_data(tdms_file: TdmsFile, group_name: str) -> pd.DataFrame:
    """
    Extract all channel data from a group as a single DataFrame.
    
    Args:
        tdms_file: TdmsFile object
        group_name: Name of the group
        
    Returns:
        DataFrame with all channels in the group
    """
    group = tdms_file[group_name]
    channels = get_channels(tdms_file, group_name)
    
    # Collect all channel data
    data_dict = {}
    
    for channel_name in channels:
        channel = group[channel_name]
        data_dict[channel_name] = channel.data
    
    # Create DataFrame
    df = pd.DataFrame(data_dict)
    
    return df


def get_file_metadata(tdms_file: TdmsFile) -> Dict[str, Any]:
    """
    Get metadata from TDMS file.
    
    Args:
        tdms_file: TdmsFile object
        
    Returns:
        Dictionary with file metadata
    """
    metadata = {
        'groups': get_groups(tdms_file),
        'group_details': {}
    }
    
    for group_name in metadata['groups']:
        channels = get_channels(tdms_file, group_name)
        metadata['group_details'][group_name] = {
            'channels': channels,
            'channel_count': len(channels)
        }
    
    return metadata


def _safe_properties(properties: Any) -> Dict[str, Any]:
    """Convert a TDMS properties object to a regular dictionary."""
    if properties is None:
        return {}

    try:
        return dict(properties)
    except Exception:
        return {}


def get_tdms_structure(tdms_file: TdmsFile) -> Dict[str, Any]:
    """Return a GUI-friendly summary of the file, groups, channels, and properties."""
    structure: Dict[str, Any] = {
        'file_properties': _safe_properties(getattr(tdms_file, 'properties', None)),
        'groups': [],
    }

    for group in tdms_file.groups():
        group_entry: Dict[str, Any] = {
            'name': group.name,
            'properties': _safe_properties(getattr(group, 'properties', None)),
            'channels': [],
        }

        for channel in group.channels():
            data = getattr(channel, 'data', None)
            if data is None or len(data) == 0:
                min_value = None
                max_value = None
            else:
                try:
                    min_value = data.min()
                    max_value = data.max()
                except Exception:
                    min_value = None
                    max_value = None

            group_entry['channels'].append({
                'name': channel.name,
                'properties': _safe_properties(getattr(channel, 'properties', None)),
                'length': len(channel.data) if getattr(channel, 'data', None) is not None else 0,
                'min': min_value,
                'max': max_value,
            })

        structure['groups'].append(group_entry)

    return structure
