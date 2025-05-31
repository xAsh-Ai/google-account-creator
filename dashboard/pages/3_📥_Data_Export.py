"""
Data Export Page - Google Account Creator Dashboard

Comprehensive data export and download functionality with advanced filtering,
multiple export formats, scheduled exports, and data archiving features.

Features:
- Multiple export formats (CSV, JSON, Excel, PDF)
- Advanced filtering and date range selection
- Bulk data export with progress tracking
- Scheduled export functionality
- Data compression and archiving
- Export history and management
- Custom report generation
"""

import streamlit as st
import pandas as pd
import json
import io
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import sys
import base64
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger

# Initialize logger
logger = get_logger("DataExportPage")

# Page configuration
st.set_page_config(
    page_title="Data Export - Google Account Creator",
    page_icon="📥",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .export-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border: 1px solid #e9ecef;
    }
    
    .export-option {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 4px solid #007bff;
    }
    
    .format-selector {
        display: flex;
        gap: 1rem;
        margin: 1rem 0;
    }
    
    .format-card {
        background: white;
        border: 2px solid #e9ecef;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .format-card:hover {
        border-color: #007bff;
        background: #f8f9fa;
    }
    
    .format-card.selected {
        border-color: #007bff;
        background: #e3f2fd;
    }
    
    .progress-bar {
        background: #e9ecef;
        border-radius: 4px;
        height: 20px;
        overflow: hidden;
    }
    
    .progress-fill {
        background: linear-gradient(90deg, #007bff, #28a745);
        height: 100%;
        transition: width 0.3s ease;
    }
    
    .export-history {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    
    .warning-message {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #ffeaa7;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

class DataExportManager:
    """Manages data export functionality"""
    
    def __init__(self):
        self.export_formats = {
            'csv': {'name': 'CSV', 'icon': '📊', 'description': 'Comma-separated values'},
            'json': {'name': 'JSON', 'icon': '🔗', 'description': 'JavaScript Object Notation'},
            'excel': {'name': 'Excel', 'icon': '📈', 'description': 'Microsoft Excel format'},
            'pdf': {'name': 'PDF', 'icon': '📄', 'description': 'Portable Document Format'}
        }
        
        self.data_types = {
            'accounts': 'Account Creation Data',
            'devices': 'Device Status Information',
            'statistics': 'Performance Statistics',
            'logs': 'System Logs',
            'survival': 'Account Survival Rates',
            'geographic': 'Geographic Distribution'
        }
    
    def generate_sample_data(self, data_type: str, days: int = 30) -> pd.DataFrame:
        """Generate sample data for export"""
        import numpy as np
        import random
        
        base_date = datetime.now().date()
        
        if data_type == 'accounts':
            data = []
            for i in range(days):
                date = base_date - timedelta(days=i)
                accounts_created = random.randint(15, 35)
                
                for j in range(accounts_created):
                    data.append({
                        'account_id': f'acc_{date.strftime("%Y%m%d")}_{j+1:03d}',
                        'creation_date': date,
                        'creation_time': f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}",
                        'status': random.choice(['active', 'suspended', 'deleted']),
                        'creation_method': random.choice(['standard', 'verified_phone', 'verified_email', 'full_verification']),
                        'location': random.choice(['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix']),
                        'device_id': f'device-{random.randint(1, 8):03d}',
                        'success_rate': random.uniform(75, 98),
                        'survival_24h': random.choice([True, False]),
                        'survival_7d': random.choice([True, False]),
                        'survival_30d': random.choice([True, False]),
                        'last_activity': date + timedelta(days=random.randint(0, 7))
                    })
            return pd.DataFrame(data)
        
        elif data_type == 'devices':
            devices = []
            for i in range(8):
                device_data = []
                for j in range(days):
                    date = base_date - timedelta(days=j)
                    device_data.append({
                        'device_id': f'device-{i+1:03d}',
                        'device_name': f'Creator {i+1}',
                        'date': date,
                        'status': random.choice(['active', 'idle', 'maintenance', 'error']),
                        'cpu_usage': random.uniform(20, 85),
                        'memory_usage': random.uniform(30, 90),
                        'disk_usage': random.uniform(40, 80),
                        'network_usage': random.uniform(10, 95),
                        'accounts_created': random.randint(0, 25),
                        'uptime_hours': random.randint(0, 24),
                        'errors_count': random.randint(0, 5),
                        'health_score': random.uniform(60, 100),
                        'location': random.choice(['New York', 'Los Angeles', 'London', 'Tokyo'])
                    })
                devices.extend(device_data)
            return pd.DataFrame(devices)
        
        elif data_type == 'statistics':
            stats = []
            for i in range(days):
                date = base_date - timedelta(days=i)
                stats.append({
                    'date': date,
                    'total_accounts_created': random.randint(50, 150),
                    'successful_accounts': random.randint(40, 140),
                    'failed_accounts': random.randint(5, 20),
                    'success_rate': random.uniform(75, 95),
                    'avg_creation_time': random.uniform(30, 120),
                    'peak_hour': random.randint(9, 17),
                    'devices_active': random.randint(5, 8),
                    'total_errors': random.randint(0, 10),
                    'system_uptime': random.uniform(95, 100)
                })
            return pd.DataFrame(stats)
        
        elif data_type == 'survival':
            survival = []
            for i in range(days):
                date = base_date - timedelta(days=i)
                survival.append({
                    'date': date,
                    'accounts_created': random.randint(20, 40),
                    'survival_24h_count': random.randint(18, 38),
                    'survival_7d_count': random.randint(15, 35),
                    'survival_30d_count': random.randint(12, 30),
                    'survival_24h_rate': random.uniform(85, 98),
                    'survival_7d_rate': random.uniform(75, 90),
                    'survival_30d_rate': random.uniform(65, 85),
                    'method_standard': random.randint(8, 15),
                    'method_verified': random.randint(5, 12),
                    'method_full': random.randint(2, 8)
                })
            return pd.DataFrame(survival)
        
        else:
            # Default generic data
            return pd.DataFrame({
                'date': [base_date - timedelta(days=i) for i in range(days)],
                'value': [random.randint(10, 100) for _ in range(days)]
            })
    
    def export_to_csv(self, df: pd.DataFrame) -> str:
        """Export dataframe to CSV format"""
        return df.to_csv(index=False)
    
    def export_to_json(self, df: pd.DataFrame) -> str:
        """Export dataframe to JSON format"""
        return df.to_json(orient='records', date_format='iso', indent=2)
    
    def export_to_excel(self, df: pd.DataFrame) -> bytes:
        """Export dataframe to Excel format"""
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Data')
        return output.getvalue()
    
    def create_zip_archive(self, files: Dict[str, bytes]) -> bytes:
        """Create a ZIP archive containing multiple files"""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, file_data in files.items():
                zip_file.writestr(filename, file_data)
        return zip_buffer.getvalue()
    
    def generate_export_metadata(self, export_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate metadata for the export"""
        return {
            'export_timestamp': datetime.now().isoformat(),
            'export_config': export_config,
            'data_types': export_config.get('data_types', []),
            'date_range': {
                'start': export_config.get('start_date', '').isoformat() if export_config.get('start_date') else None,
                'end': export_config.get('end_date', '').isoformat() if export_config.get('end_date') else None
            },
            'format': export_config.get('format', 'csv'),
            'total_records': export_config.get('total_records', 0),
            'filters_applied': export_config.get('filters', {}),
            'exported_by': 'Google Account Creator Dashboard',
            'version': '1.0'
        }

def render_export_configuration():
    """Render export configuration section"""
    st.markdown("### 🔧 Export Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Data Selection")
        
        data_types = st.multiselect(
            "Select data types to export:",
            options=list(DataExportManager().data_types.keys()),
            format_func=lambda x: DataExportManager().data_types[x],
            default=['accounts', 'statistics']
        )
        
        st.markdown("#### 📅 Date Range")
        date_range = st.selectbox(
            "Select date range:",
            ["Last 7 days", "Last 30 days", "Last 90 days", "Custom range"]
        )
        
        if date_range == "Custom range":
            col_start, col_end = st.columns(2)
            with col_start:
                start_date = st.date_input("Start date", value=datetime.now().date() - timedelta(days=30))
            with col_end:
                end_date = st.date_input("End date", value=datetime.now().date())
        else:
            days_map = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90}
            days = days_map[date_range]
            start_date = datetime.now().date() - timedelta(days=days)
            end_date = datetime.now().date()
    
    with col2:
        st.markdown("#### 📄 Export Format")
        
        export_manager = DataExportManager()
        selected_format = st.radio(
            "Choose export format:",
            options=list(export_manager.export_formats.keys()),
            format_func=lambda x: f"{export_manager.export_formats[x]['icon']} {export_manager.export_formats[x]['name']} - {export_manager.export_formats[x]['description']}"
        )
        
        st.markdown("#### ⚙️ Advanced Options")
        
        include_metadata = st.checkbox("Include export metadata", value=True)
        compress_data = st.checkbox("Compress exported data", value=False)
        
        if len(data_types) > 1:
            separate_files = st.checkbox("Export each data type as separate file", value=True)
        else:
            separate_files = False
    
    return {
        'data_types': data_types,
        'start_date': start_date,
        'end_date': end_date,
        'format': selected_format,
        'include_metadata': include_metadata,
        'compress_data': compress_data,
        'separate_files': separate_files
    }

def render_export_preview(export_config: Dict[str, Any]):
    """Render preview of data to be exported"""
    if not export_config['data_types']:
        st.warning("⚠️ Please select at least one data type to preview.")
        return None
    
    st.markdown("### 👀 Export Preview")
    
    export_manager = DataExportManager()
    
    # Calculate date range
    days = (export_config['end_date'] - export_config['start_date']).days + 1
    
    total_records = 0
    preview_data = {}
    
    for data_type in export_config['data_types']:
        df = export_manager.generate_sample_data(data_type, min(days, 30))  # Limit preview
        preview_data[data_type] = df
        total_records += len(df)
        
        # Show preview for first data type
        if data_type == export_config['data_types'][0]:
            st.markdown(f"#### Sample: {export_manager.data_types[data_type]}")
            st.dataframe(df.head(10), use_container_width=True)
            if len(df) > 10:
                st.info(f"Showing 10 of {len(df)} records for this data type.")
    
    # Export summary
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Data Types", len(export_config['data_types']))
    with col2:
        st.metric("Total Records", f"{total_records:,}")
    with col3:
        estimated_size = total_records * 0.5  # Rough estimate in KB
        if estimated_size > 1024:
            size_str = f"{estimated_size/1024:.1f} MB"
        else:
            size_str = f"{estimated_size:.0f} KB"
        st.metric("Estimated Size", size_str)
    
    return preview_data

def render_export_execution(export_config: Dict[str, Any], preview_data: Dict[str, pd.DataFrame]):
    """Render export execution section"""
    st.markdown("### 🚀 Execute Export")
    
    if not preview_data:
        st.warning("⚠️ No data available for export. Please configure your export settings.")
        return
    
    export_manager = DataExportManager()
    
    # Export options
    col1, col2 = st.columns([3, 1])
    
    with col1:
        export_name = st.text_input(
            "Export name (optional):",
            placeholder="My Export " + datetime.now().strftime("%Y-%m-%d")
        )
    
    with col2:
        if st.button("🚀 Start Export", type="primary", use_container_width=True):
            execute_export(export_config, preview_data, export_name or "export")

def execute_export(export_config: Dict[str, Any], preview_data: Dict[str, pd.DataFrame], export_name: str):
    """Execute the export process"""
    export_manager = DataExportManager()
    
    # Progress tracking
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("🔄 Preparing export...")
        progress_bar.progress(10)
        
        files_to_export = {}
        total_records = sum(len(df) for df in preview_data.values())
        
        # Process each data type
        for i, (data_type, df) in enumerate(preview_data.items()):
            status_text.text(f"🔄 Processing {export_manager.data_types[data_type]}...")
            progress = 20 + (i * 50 // len(preview_data))
            progress_bar.progress(progress)
            
            # Generate filename
            if export_config['separate_files'] and len(preview_data) > 1:
                base_filename = f"{export_name}_{data_type}"
            else:
                base_filename = export_name
            
            # Export based on format
            if export_config['format'] == 'csv':
                file_data = export_manager.export_to_csv(df).encode('utf-8')
                filename = f"{base_filename}.csv"
            elif export_config['format'] == 'json':
                file_data = export_manager.export_to_json(df).encode('utf-8')
                filename = f"{base_filename}.json"
            elif export_config['format'] == 'excel':
                file_data = export_manager.export_to_excel(df)
                filename = f"{base_filename}.xlsx"
            else:
                st.error(f"❌ Unsupported format: {export_config['format']}")
                return
            
            files_to_export[filename] = file_data
        
        # Add metadata if requested
        if export_config['include_metadata']:
            status_text.text("🔄 Generating metadata...")
            progress_bar.progress(75)
            
            export_config['total_records'] = total_records
            metadata = export_manager.generate_export_metadata(export_config)
            metadata_json = json.dumps(metadata, indent=2, default=str).encode('utf-8')
            files_to_export[f"{export_name}_metadata.json"] = metadata_json
        
        # Finalize export
        status_text.text("🔄 Finalizing export...")
        progress_bar.progress(90)
        
        if export_config['compress_data'] or len(files_to_export) > 1:
            # Create ZIP archive
            final_data = export_manager.create_zip_archive(files_to_export)
            final_filename = f"{export_name}.zip"
            mime_type = "application/zip"
        else:
            # Single file
            final_filename = list(files_to_export.keys())[0]
            final_data = list(files_to_export.values())[0]
            mime_type = {
                'csv': 'text/csv',
                'json': 'application/json',
                'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }.get(export_config['format'], 'application/octet-stream')
        
        # Complete
        progress_bar.progress(100)
        status_text.text("✅ Export completed successfully!")
        
        # Download button
        st.download_button(
            label=f"📥 Download {final_filename}",
            data=final_data,
            file_name=final_filename,
            mime=mime_type,
            type="primary"
        )
        
        # Show success message
        st.success(f"""
        ✅ **Export Completed Successfully!**
        
        - **File:** {final_filename}
        - **Size:** {len(final_data) / 1024:.1f} KB
        - **Records:** {total_records:,}
        - **Format:** {export_config['format'].upper()}
        - **Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """)
        
        # Log export
        logger.info(f"Export completed: {final_filename}, {total_records} records, {len(final_data)} bytes")
        
    except Exception as e:
        progress_bar.progress(0)
        status_text.text("❌ Export failed!")
        st.error(f"❌ Export failed: {str(e)}")
        logger.error(f"Export failed: {str(e)}")

def render_export_history():
    """Render export history section"""
    st.markdown("### 📋 Export History")
    
    # Sample export history
    history_data = [
        {
            'timestamp': datetime.now() - timedelta(hours=2),
            'name': 'Daily Account Report',
            'data_types': ['accounts', 'statistics'],
            'format': 'csv',
            'size': '2.3 MB',
            'records': 1247,
            'status': 'completed'
        },
        {
            'timestamp': datetime.now() - timedelta(days=1),
            'name': 'Device Performance Export',
            'data_types': ['devices'],
            'format': 'excel',
            'size': '1.8 MB',
            'records': 856,
            'status': 'completed'
        },
        {
            'timestamp': datetime.now() - timedelta(days=3),
            'name': 'Weekly Statistics',
            'data_types': ['statistics', 'survival'],
            'format': 'json',
            'size': '945 KB',
            'records': 2341,
            'status': 'completed'
        },
        {
            'timestamp': datetime.now() - timedelta(days=7),
            'name': 'Monthly Report',
            'data_types': ['accounts', 'devices', 'statistics'],
            'format': 'csv',
            'size': '5.7 MB',
            'records': 4567,
            'status': 'completed'
        }
    ]
    
    if history_data:
        # Convert to DataFrame for display
        df_history = pd.DataFrame(history_data)
        df_history['timestamp'] = df_history['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        df_history['data_types'] = df_history['data_types'].apply(lambda x: ', '.join(x))
        
        # Rename columns for display
        df_display = df_history.rename(columns={
            'timestamp': 'Date & Time',
            'name': 'Export Name',
            'data_types': 'Data Types',
            'format': 'Format',
            'size': 'Size',
            'records': 'Records',
            'status': 'Status'
        })
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Bulk actions
        st.markdown("#### 🛠️ Bulk Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🗑️ Clear History"):
                st.warning("⚠️ This would clear all export history. Confirmation required.")
        
        with col2:
            if st.button("📊 Export History"):
                history_csv = df_display.to_csv(index=False)
                st.download_button(
                    label="📥 Download History CSV",
                    data=history_csv,
                    file_name=f"export_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        with col3:
            if st.button("🔄 Refresh History"):
                st.rerun()
    else:
        st.info("📭 No export history available.")

def render_scheduled_exports():
    """Render scheduled exports section"""
    st.markdown("### ⏰ Scheduled Exports")
    
    # Sample scheduled exports
    scheduled_exports = [
        {
            'name': 'Daily Statistics Report',
            'schedule': 'Daily at 09:00',
            'data_types': ['statistics'],
            'format': 'csv',
            'next_run': datetime.now() + timedelta(hours=8),
            'status': 'active'
        },
        {
            'name': 'Weekly Device Report',
            'schedule': 'Every Monday at 08:00',
            'data_types': ['devices'],
            'format': 'excel',
            'next_run': datetime.now() + timedelta(days=2),
            'status': 'active'
        },
        {
            'name': 'Monthly Full Export',
            'schedule': '1st of every month at 07:00',
            'data_types': ['accounts', 'devices', 'statistics'],
            'format': 'json',
            'next_run': datetime.now() + timedelta(days=15),
            'status': 'paused'
        }
    ]
    
    if scheduled_exports:
        for i, export in enumerate(scheduled_exports):
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    status_icon = "🟢" if export['status'] == 'active' else "⏸️"
                    st.markdown(f"**{status_icon} {export['name']}**")
                    st.markdown(f"📅 {export['schedule']}")
                    st.markdown(f"📊 {', '.join(export['data_types'])} ({export['format'].upper()})")
                
                with col2:
                    st.markdown(f"**Next Run:** {export['next_run'].strftime('%Y-%m-%d %H:%M')}")
                    st.markdown(f"**Status:** {export['status'].title()}")
                
                with col3:
                    if st.button("⚙️", key=f"config_{i}", help="Configure"):
                        st.info(f"Configure {export['name']}")
                    if st.button("⏸️" if export['status'] == 'active' else "▶️", 
                               key=f"toggle_{i}", 
                               help="Pause/Resume"):
                        st.success(f"{'Paused' if export['status'] == 'active' else 'Resumed'} {export['name']}")
                
                if i < len(scheduled_exports) - 1:
                    st.markdown("---")
    
    # Add new scheduled export
    st.markdown("#### ➕ Add New Scheduled Export")
    
    with st.expander("Create Scheduled Export"):
        schedule_name = st.text_input("Export name:")
        schedule_frequency = st.selectbox(
            "Frequency:",
            ["Daily", "Weekly", "Monthly", "Custom"]
        )
        
        if schedule_frequency == "Custom":
            st.text_input("Cron expression:", placeholder="0 9 * * *")
        
        schedule_data_types = st.multiselect(
            "Data types:",
            options=list(DataExportManager().data_types.keys()),
            format_func=lambda x: DataExportManager().data_types[x]
        )
        
        schedule_format = st.selectbox(
            "Export format:",
            ["csv", "json", "excel"]
        )
        
        if st.button("➕ Create Scheduled Export"):
            st.success(f"✅ Created scheduled export: {schedule_name}")

def main():
    """Main data export page function"""
    st.title("📥 Data Export & Download")
    st.markdown("Comprehensive data export functionality with advanced filtering and multiple formats")
    
    # Sidebar filters
    st.sidebar.markdown("### 🔍 Quick Filters")
    quick_export = st.sidebar.selectbox(
        "Quick Export Templates:",
        ["Custom Export", "Daily Report", "Weekly Summary", "Monthly Archive", "Device Status", "Account Analytics"]
    )
    
    if quick_export != "Custom Export":
        st.sidebar.info(f"📋 Using template: **{quick_export}**")
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["🔧 Configure Export", "📋 Export History", "⏰ Scheduled Exports"])
    
    with tab1:
        # Export configuration
        export_config = render_export_configuration()
        
        st.markdown("---")
        
        # Preview data
        preview_data = render_export_preview(export_config)
        
        if preview_data:
            st.markdown("---")
            
            # Execute export
            render_export_execution(export_config, preview_data)
    
    with tab2:
        render_export_history()
    
    with tab3:
        render_scheduled_exports()
    
    # Footer with tips
    st.markdown("---")
    st.markdown("### 💡 Export Tips")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("""
        **📊 CSV Format**
        - Best for data analysis
        - Compatible with Excel
        - Lightweight file size
        """)
    
    with col2:
        st.info("""
        **🔗 JSON Format**
        - Machine-readable
        - Preserves data structure
        - API-friendly
        """)
    
    with col3:
        st.info("""
        **📈 Excel Format**
        - Rich formatting options
        - Multiple sheets support
        - Business-friendly
        """)

if __name__ == "__main__":
    main() 