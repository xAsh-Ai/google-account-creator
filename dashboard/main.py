"""
Google Account Creator Dashboard

A comprehensive web dashboard for monitoring Google account creation system
using Streamlit framework.

Features:
- Overall system status monitoring
- Account creation statistics and analytics
- Device status and performance tracking
- Account survival rate analysis
- Real-time data updates
- Data export functionality
- Mobile-responsive design
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger
from core.database import DatabaseManager
from core.config_manager import ConfigManager

# Initialize logger
logger = get_logger("Dashboard")

# Page configuration
st.set_page_config(
    page_title="Google Account Creator Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #1f77b4;
    }
    
    .status-good {
        color: #28a745;
        font-weight: bold;
    }
    
    .status-warning {
        color: #ffc107;
        font-weight: bold;
    }
    
    .status-error {
        color: #dc3545;
        font-weight: bold;
    }
    
    .sidebar .element-container {
        margin-bottom: 1rem;
    }
    
    .stMetric {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

class DashboardData:
    """Handles data fetching and processing for the dashboard"""
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.db_manager = None
        self._initialize_database()
    
    def _initialize_database(self):
        """Initialize database connection if available"""
        try:
            self.db_manager = DatabaseManager()
        except Exception as e:
            logger.warning(f"Database connection failed: {e}")
            self.db_manager = None
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        status = {
            'timestamp': datetime.now(),
            'overall_status': 'healthy',
            'services': {
                'account_creator': {'status': 'running', 'uptime': '2d 15h 32m'},
                'database': {'status': 'connected', 'connections': 5},
                'logging_system': {'status': 'active', 'logs_processed': 15420},
                'web_dashboard': {'status': 'running', 'users_active': 3}
            },
            'alerts': []
        }
        
        # Check database connection
        if not self.db_manager:
            status['services']['database']['status'] = 'disconnected'
            status['alerts'].append({
                'level': 'warning',
                'message': 'Database connection unavailable',
                'timestamp': datetime.now()
            })
            status['overall_status'] = 'degraded'
        
        # Check configuration
        try:
            config = self.config_manager.get_all_config()
            if not config.get('anthropic_api_key') and not config.get('openai_api_key'):
                status['alerts'].append({
                    'level': 'error',
                    'message': 'No AI API keys configured',
                    'timestamp': datetime.now()
                })
                status['overall_status'] = 'error'
        except Exception:
            status['alerts'].append({
                'level': 'warning',
                'message': 'Configuration system unavailable',
                'timestamp': datetime.now()
            })
        
        return status
    
    def get_account_statistics(self) -> Dict[str, Any]:
        """Get account creation statistics"""
        # Sample data - in real implementation, this would come from database
        today = datetime.now().date()
        
        stats = {
            'total_accounts': 1247,
            'today_created': 23,
            'success_rate': 87.5,
            'active_accounts': 1089,
            'failed_accounts': 158,
            'pending_accounts': 45,
            'daily_stats': []
        }
        
        # Generate daily stats for the last 30 days
        for i in range(30):
            date = today - timedelta(days=i)
            accounts_created = max(0, int(25 + (i % 7) * 3 - (i % 13)))
            success_rate = max(75, min(95, 85 + (i % 5) * 2))
            
            stats['daily_stats'].append({
                'date': date,
                'accounts_created': accounts_created,
                'success_rate': success_rate,
                'failures': max(0, int(accounts_created * (100 - success_rate) / 100))
            })
        
        stats['daily_stats'].reverse()  # Most recent first
        
        return stats
    
    def get_device_status(self) -> List[Dict[str, Any]]:
        """Get device status information"""
        devices = [
            {
                'id': 'device-001',
                'name': 'Primary Creator',
                'status': 'active',
                'cpu_usage': 45.2,
                'memory_usage': 67.8,
                'accounts_created_today': 12,
                'last_seen': datetime.now() - timedelta(minutes=2),
                'ip_address': '192.168.1.100',
                'location': 'New York, NY'
            },
            {
                'id': 'device-002',
                'name': 'Secondary Creator',
                'status': 'active',
                'cpu_usage': 32.1,
                'memory_usage': 54.3,
                'accounts_created_today': 8,
                'last_seen': datetime.now() - timedelta(minutes=5),
                'ip_address': '192.168.1.101',
                'location': 'Los Angeles, CA'
            },
            {
                'id': 'device-003',
                'name': 'Backup Creator',
                'status': 'idle',
                'cpu_usage': 15.7,
                'memory_usage': 23.1,
                'accounts_created_today': 3,
                'last_seen': datetime.now() - timedelta(minutes=15),
                'ip_address': '192.168.1.102',
                'location': 'Chicago, IL'
            },
            {
                'id': 'device-004',
                'name': 'Test Environment',
                'status': 'maintenance',
                'cpu_usage': 8.3,
                'memory_usage': 12.4,
                'accounts_created_today': 0,
                'last_seen': datetime.now() - timedelta(hours=2),
                'ip_address': '192.168.1.103',
                'location': 'Austin, TX'
            }
        ]
        
        return devices
    
    def get_survival_rates(self) -> Dict[str, Any]:
        """Get account survival rate data"""
        return {
            '24_hour': 94.2,
            '7_day': 89.1,
            '30_day': 82.7,
            '90_day': 76.3,
            'by_creation_method': {
                'standard': 85.4,
                'verified_phone': 91.2,
                'verified_email': 88.7,
                'full_verification': 94.8
            },
            'by_activity_level': {
                'high_activity': 92.1,
                'medium_activity': 86.5,
                'low_activity': 71.8,
                'no_activity': 58.3
            }
        }

def render_system_status(data: DashboardData):
    """Render the system status section"""
    st.markdown('<div class="main-header">', unsafe_allow_html=True)
    st.markdown("### 🎯 Google Account Creator Dashboard")
    st.markdown("Real-time system monitoring and analytics")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Get system status
    status = data.get_system_status()
    
    # Overall status indicator
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status_color = {
            'healthy': '🟢',
            'degraded': '🟡',
            'error': '🔴'
        }.get(status['overall_status'], '🔴')
        
        st.metric(
            label="System Status",
            value=f"{status_color} {status['overall_status'].title()}"
        )
    
    with col2:
        st.metric(
            label="Active Services",
            value=f"{len([s for s in status['services'].values() if s['status'] in ['running', 'active', 'connected']])}/{len(status['services'])}"
        )
    
    with col3:
        st.metric(
            label="Active Alerts",
            value=len(status['alerts'])
        )
    
    with col4:
        st.metric(
            label="Last Update",
            value=status['timestamp'].strftime("%H:%M:%S")
        )
    
    # Service details
    st.markdown("### 🔧 Service Status")
    
    service_cols = st.columns(2)
    
    for i, (service_name, service_info) in enumerate(status['services'].items()):
        with service_cols[i % 2]:
            status_icon = {
                'running': '🟢',
                'active': '🟢',
                'connected': '🟢',
                'idle': '🟡',
                'disconnected': '🔴',
                'error': '🔴'
            }.get(service_info['status'], '🔴')
            
            st.markdown(f"""
            **{status_icon} {service_name.replace('_', ' ').title()}**
            - Status: {service_info['status']}
            """ + (f"- Uptime: {service_info.get('uptime', 'N/A')}" if 'uptime' in service_info else "") +
            (f"- Connections: {service_info.get('connections', 'N/A')}" if 'connections' in service_info else "") +
            (f"- Logs Processed: {service_info.get('logs_processed', 'N/A'):,}" if 'logs_processed' in service_info else "") +
            (f"- Active Users: {service_info.get('users_active', 'N/A')}" if 'users_active' in service_info else "")
            )
    
    # Alerts section
    if status['alerts']:
        st.markdown("### 🚨 Active Alerts")
        for alert in status['alerts']:
            alert_color = {
                'info': 'info',
                'warning': 'warning', 
                'error': 'error'
            }.get(alert['level'], 'error')
            
            st.warning(f"**{alert['level'].upper()}**: {alert['message']}")

def render_quick_stats(data: DashboardData):
    """Render quick statistics overview"""
    stats = data.get_account_statistics()
    
    st.markdown("### 📊 Quick Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Accounts",
            value=f"{stats['total_accounts']:,}",
            delta=f"+{stats['today_created']} today"
        )
    
    with col2:
        st.metric(
            label="Success Rate",
            value=f"{stats['success_rate']:.1f}%",
            delta="2.3%" if stats['success_rate'] > 85 else "-1.2%"
        )
    
    with col3:
        st.metric(
            label="Active Accounts",
            value=f"{stats['active_accounts']:,}",
            delta=f"{stats['active_accounts']/stats['total_accounts']*100:.1f}%"
        )
    
    with col4:
        st.metric(
            label="Failed Accounts",
            value=f"{stats['failed_accounts']:,}",
            delta=f"{stats['failed_accounts']/stats['total_accounts']*100:.1f}%"
        )

def render_charts(data: DashboardData):
    """Render charts and visualizations"""
    stats = data.get_account_statistics()
    survival_data = data.get_survival_rates()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📈 Daily Account Creation")
        
        # Prepare data for chart
        df_daily = pd.DataFrame(stats['daily_stats'])
        df_daily['date'] = pd.to_datetime(df_daily['date'])
        
        fig = px.line(
            df_daily.tail(14),  # Last 14 days
            x='date',
            y='accounts_created',
            title='Accounts Created (Last 14 Days)',
            markers=True
        )
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Accounts Created",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📉 Success Rate Trend")
        
        fig = px.line(
            df_daily.tail(14),
            x='date',
            y='success_rate',
            title='Success Rate (Last 14 Days)',
            markers=True,
            color_discrete_sequence=['#28a745']
        )
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Success Rate (%)",
            height=400,
            yaxis=dict(range=[70, 100])
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Survival rates chart
    st.markdown("### 🎯 Account Survival Rates")
    
    col3, col4 = st.columns(2)
    
    with col3:
        # Time-based survival rates
        survival_periods = ['24 Hour', '7 Day', '30 Day', '90 Day']
        survival_rates = [
            survival_data['24_hour'],
            survival_data['7_day'],
            survival_data['30_day'],
            survival_data['90_day']
        ]
        
        fig = px.bar(
            x=survival_periods,
            y=survival_rates,
            title='Survival Rate by Time Period',
            color=survival_rates,
            color_continuous_scale='RdYlGn'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col4:
        # Survival by creation method
        methods = list(survival_data['by_creation_method'].keys())
        rates = list(survival_data['by_creation_method'].values())
        
        fig = px.pie(
            values=rates,
            names=[m.replace('_', ' ').title() for m in methods],
            title='Survival Rate by Creation Method'
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

def main():
    """Main dashboard application"""
    # Initialize data handler
    data = DashboardData()
    
    # Sidebar
    st.sidebar.title("🎯 Dashboard Navigation")
    
    # Auto-refresh option
    auto_refresh = st.sidebar.checkbox("Auto Refresh (30s)", value=False)
    
    if auto_refresh:
        time.sleep(30)
        st.rerun()
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()
    
    # Time range selector
    st.sidebar.markdown("### 📅 Time Range")
    time_range = st.sidebar.selectbox(
        "Select time range:",
        ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "Last 90 Days"],
        index=1
    )
    
    # Export options
    st.sidebar.markdown("### 📥 Export Data")
    if st.sidebar.button("📊 Export Statistics"):
        stats = data.get_account_statistics()
        df = pd.DataFrame(stats['daily_stats'])
        csv = df.to_csv(index=False)
        st.sidebar.download_button(
            label="Download CSV",
            data=csv,
            file_name=f"account_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    # Main content
    render_system_status(data)
    
    st.markdown("---")
    
    render_quick_stats(data)
    
    st.markdown("---")
    
    render_charts(data)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; padding: 1rem;'>"
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
        "Google Account Creator Dashboard v1.0"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main() 