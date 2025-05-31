"""
Device Status Page - Google Account Creator Dashboard

Comprehensive device monitoring and management page with real-time
performance metrics, geographic distribution, and device-specific analytics.

Features:
- Real-time device status monitoring
- Performance metrics (CPU, Memory, Network)
- Geographic device distribution
- Device-specific account creation statistics
- Alert management for device issues
- Device health scoring
- Historical performance trends
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys
import random

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger

# Initialize logger
logger = get_logger("DeviceStatusPage")

# Page configuration
st.set_page_config(
    page_title="Device Status - Google Account Creator",
    page_icon="🖥️",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .device-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 5px solid;
    }
    
    .device-active {
        border-left-color: #28a745;
    }
    
    .device-idle {
        border-left-color: #ffc107;
    }
    
    .device-maintenance {
        border-left-color: #6c757d;
    }
    
    .device-error {
        border-left-color: #dc3545;
    }
    
    .performance-metric {
        background: #f8f9fa;
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.25rem 0;
    }
    
    .status-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
    }
    
    .status-active { background-color: #28a745; }
    .status-idle { background-color: #ffc107; }
    .status-maintenance { background-color: #6c757d; }
    .status-error { background-color: #dc3545; }
    
    .metric-good { color: #28a745; font-weight: bold; }
    .metric-warning { color: #ffc107; font-weight: bold; }
    .metric-critical { color: #dc3545; font-weight: bold; }
    
    .health-score {
        font-size: 2rem;
        font-weight: bold;
        text-align: center;
    }
    
    .health-excellent { color: #28a745; }
    .health-good { color: #20c997; }
    .health-fair { color: #ffc107; }
    .health-poor { color: #fd7e14; }
    .health-critical { color: #dc3545; }
</style>
""", unsafe_allow_html=True)

class DeviceManager:
    """Manages device data and monitoring"""
    
    def __init__(self):
        self.device_names = [
            "Primary Creator", "Secondary Creator", "Backup Creator", 
            "Test Environment", "Mobile Creator", "Cloud Instance A",
            "Cloud Instance B", "Development Box"
        ]
        
        self.locations = [
            "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX",
            "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX", "San Diego, CA",
            "Dallas, TX", "San Jose, CA", "Austin, TX", "Jacksonville, FL",
            "London, UK", "Paris, France", "Tokyo, Japan", "Singapore",
            "Sydney, Australia", "Toronto, Canada", "Mumbai, India", "São Paulo, Brazil"
        ]
        
        self.device_statuses = ["active", "idle", "maintenance", "error"]
    
    def generate_device_data(self, count: int = 8) -> list:
        """Generate comprehensive device data"""
        devices = []
        
        for i in range(count):
            device_id = f"device-{i+1:03d}"
            name = self.device_names[i % len(self.device_names)]
            if i >= len(self.device_names):
                name += f" {i - len(self.device_names) + 2}"
            
            # Device status with realistic distribution
            status_weights = [0.6, 0.2, 0.15, 0.05]  # active, idle, maintenance, error
            status = np.random.choice(self.device_statuses, p=status_weights)
            
            # Performance metrics based on status
            if status == "active":
                cpu_usage = np.random.uniform(30, 85)
                memory_usage = np.random.uniform(40, 90)
                accounts_today = np.random.randint(8, 25)
                last_seen_minutes = np.random.randint(1, 10)
            elif status == "idle":
                cpu_usage = np.random.uniform(5, 25)
                memory_usage = np.random.uniform(20, 50)
                accounts_today = np.random.randint(0, 8)
                last_seen_minutes = np.random.randint(10, 60)
            elif status == "maintenance":
                cpu_usage = np.random.uniform(5, 20)
                memory_usage = np.random.uniform(10, 30)
                accounts_today = 0
                last_seen_minutes = np.random.randint(60, 300)
            else:  # error
                cpu_usage = np.random.uniform(0, 15)
                memory_usage = np.random.uniform(5, 25)
                accounts_today = 0
                last_seen_minutes = np.random.randint(120, 600)
            
            # Network and disk metrics
            network_usage = np.random.uniform(10, 95) if status == "active" else np.random.uniform(0, 20)
            disk_usage = np.random.uniform(40, 85)
            
            # Location and IP
            location = random.choice(self.locations)
            ip_base = f"192.168.{random.randint(1, 10)}.{random.randint(100, 200)}"
            
            # Health score calculation
            health_factors = [
                (100 - cpu_usage) * 0.25,  # CPU health
                (100 - memory_usage) * 0.25,  # Memory health
                (100 - disk_usage) * 0.2,   # Disk health
                (accounts_today / 25 * 100) * 0.15,  # Productivity
                (60 - min(last_seen_minutes, 60)) / 60 * 100 * 0.15  # Connectivity
            ]
            
            health_score = sum(health_factors)
            if status == "error":
                health_score *= 0.3
            elif status == "maintenance":
                health_score *= 0.6
            
            health_score = max(0, min(100, health_score))
            
            device = {
                'id': device_id,
                'name': name,
                'status': status,
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'disk_usage': disk_usage,
                'network_usage': network_usage,
                'accounts_created_today': accounts_today,
                'last_seen': datetime.now() - timedelta(minutes=last_seen_minutes),
                'ip_address': ip_base,
                'location': location,
                'health_score': health_score,
                'uptime_hours': np.random.randint(1, 720) if status != "error" else 0,
                'errors_today': np.random.randint(0, 3) if status != "active" else 0,
                'success_rate_24h': np.random.uniform(85, 98) if status == "active" else np.random.uniform(60, 85)
            }
            
            devices.append(device)
        
        return devices
    
    def generate_historical_data(self, device_id: str, days: int = 7) -> pd.DataFrame:
        """Generate historical performance data for a device"""
        data = []
        base_date = datetime.now().date()
        
        for i in range(days * 24):  # Hourly data
            timestamp = datetime.combine(base_date, datetime.min.time()) - timedelta(hours=i)
            
            # Simulate daily patterns
            hour = timestamp.hour
            if 6 <= hour <= 22:  # Day time - higher activity
                cpu_base = 45
                memory_base = 60
                accounts_base = 1.5
            else:  # Night time - lower activity
                cpu_base = 25
                memory_base = 40
                accounts_base = 0.5
            
            # Add some randomness
            cpu_usage = max(5, min(95, cpu_base + np.random.uniform(-15, 25)))
            memory_usage = max(10, min(90, memory_base + np.random.uniform(-20, 20)))
            accounts_created = max(0, int(accounts_base + np.random.uniform(-1, 2)))
            
            data.append({
                'timestamp': timestamp,
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'accounts_created': accounts_created,
                'errors': 1 if np.random.random() < 0.05 else 0
            })
        
        return pd.DataFrame(data).sort_values('timestamp')

def render_device_overview(devices: list):
    """Render device overview section"""
    st.markdown("### 🖥️ Device Fleet Overview")
    
    # Fleet statistics
    total_devices = len(devices)
    active_devices = len([d for d in devices if d['status'] == 'active'])
    avg_health = np.mean([d['health_score'] for d in devices])
    total_accounts_today = sum([d['accounts_created_today'] for d in devices])
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Devices",
            value=total_devices,
            delta=f"{active_devices} active"
        )
    
    with col2:
        st.metric(
            label="Fleet Health",
            value=f"{avg_health:.0f}%",
            delta="Good" if avg_health > 75 else "Needs Attention"
        )
    
    with col3:
        st.metric(
            label="Accounts Today",
            value=total_accounts_today,
            delta=f"{total_accounts_today/active_devices:.1f} avg" if active_devices > 0 else "0 avg"
        )
    
    with col4:
        avg_cpu = np.mean([d['cpu_usage'] for d in devices if d['status'] == 'active'])
        st.metric(
            label="Avg CPU Usage",
            value=f"{avg_cpu:.0f}%",
            delta="Normal" if avg_cpu < 70 else "High"
        )

def render_device_status_grid(devices: list):
    """Render device status in a grid layout"""
    st.markdown("### 📊 Device Status Grid")
    
    # Status distribution
    status_counts = {}
    for device in devices:
        status = device['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Status overview
    col1, col2, col3, col4 = st.columns(4)
    status_colors = {
        'active': '#28a745',
        'idle': '#ffc107', 
        'maintenance': '#6c757d',
        'error': '#dc3545'
    }
    
    for i, (status, count) in enumerate(status_counts.items()):
        with [col1, col2, col3, col4][i % 4]:
            st.markdown(f"""
            <div style="text-align: center; padding: 1rem; border-radius: 8px; background: {status_colors[status]}20; border: 2px solid {status_colors[status]};">
                <h3 style="color: {status_colors[status]}; margin: 0;">{count}</h3>
                <p style="margin: 0; text-transform: capitalize;">{status}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Device cards in grid
    for i in range(0, len(devices), 2):
        col1, col2 = st.columns(2)
        
        for j, col in enumerate([col1, col2]):
            if i + j < len(devices):
                device = devices[i + j]
                render_device_card(device, col)

def render_device_card(device: dict, container):
    """Render individual device card"""
    status_class = f"device-{device['status']}"
    status_icon = {
        'active': '🟢',
        'idle': '🟡',
        'maintenance': '🔧',
        'error': '🔴'
    }[device['status']]
    
    # Health score color
    health = device['health_score']
    if health >= 90:
        health_class = "health-excellent"
    elif health >= 75:
        health_class = "health-good"
    elif health >= 60:
        health_class = "health-fair"
    elif health >= 40:
        health_class = "health-poor"
    else:
        health_class = "health-critical"
    
    with container:
        st.markdown(f"""
        <div class="device-card {status_class}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h4 style="margin: 0;">{status_icon} {device['name']}</h4>
                <div class="health-score {health_class}">{health:.0f}</div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; margin-bottom: 1rem;">
                <div class="performance-metric">
                    <strong>CPU:</strong> <span class="{'metric-critical' if device['cpu_usage'] > 80 else 'metric-warning' if device['cpu_usage'] > 60 else 'metric-good'}">{device['cpu_usage']:.0f}%</span>
                </div>
                <div class="performance-metric">
                    <strong>Memory:</strong> <span class="{'metric-critical' if device['memory_usage'] > 85 else 'metric-warning' if device['memory_usage'] > 70 else 'metric-good'}">{device['memory_usage']:.0f}%</span>
                </div>
                <div class="performance-metric">
                    <strong>Disk:</strong> <span class="{'metric-critical' if device['disk_usage'] > 90 else 'metric-warning' if device['disk_usage'] > 75 else 'metric-good'}">{device['disk_usage']:.0f}%</span>
                </div>
                <div class="performance-metric">
                    <strong>Network:</strong> <span class="{'metric-warning' if device['network_usage'] > 80 else 'metric-good'}">{device['network_usage']:.0f}%</span>
                </div>
            </div>
            
            <div style="font-size: 0.9rem; color: #666;">
                <div><strong>Location:</strong> {device['location']}</div>
                <div><strong>IP:</strong> {device['ip_address']}</div>
                <div><strong>Accounts Today:</strong> {device['accounts_created_today']}</div>
                <div><strong>Last Seen:</strong> {device['last_seen'].strftime('%H:%M:%S')}</div>
                <div><strong>Uptime:</strong> {device['uptime_hours']}h</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_performance_analytics(devices: list):
    """Render performance analytics section"""
    st.markdown("### 📈 Performance Analytics")
    
    # Create performance dataframe
    df = pd.DataFrame(devices)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CPU vs Memory scatter plot
        fig_scatter = px.scatter(
            df, 
            x='cpu_usage', 
            y='memory_usage',
            size='accounts_created_today',
            color='status',
            hover_data=['name', 'health_score'],
            title='CPU vs Memory Usage by Device'
        )
        fig_scatter.update_layout(height=400)
        st.plotly_chart(fig_scatter, use_container_width=True)
    
    with col2:
        # Health score distribution
        fig_health = px.histogram(
            df,
            x='health_score',
            nbins=10,
            title='Device Health Score Distribution',
            color_discrete_sequence=['#1f77b4']
        )
        fig_health.update_layout(height=400)
        st.plotly_chart(fig_health, use_container_width=True)
    
    # Geographic distribution
    st.markdown("### 🌍 Geographic Distribution")
    
    # Count devices by location
    location_counts = df['location'].value_counts().head(10)
    
    col3, col4 = st.columns(2)
    
    with col3:
        fig_geo = px.bar(
            x=location_counts.index,
            y=location_counts.values,
            title='Devices by Location',
            color=location_counts.values,
            color_continuous_scale='viridis'
        )
        fig_geo.update_layout(height=400)
        fig_geo.update_xaxes(tickangle=45)
        st.plotly_chart(fig_geo, use_container_width=True)
    
    with col4:
        # Accounts created by location
        location_accounts = df.groupby('location')['accounts_created_today'].sum().sort_values(ascending=False).head(10)
        
        fig_acc_geo = px.pie(
            values=location_accounts.values,
            names=location_accounts.index,
            title='Account Creation by Location'
        )
        fig_acc_geo.update_layout(height=400)
        st.plotly_chart(fig_acc_geo, use_container_width=True)

def render_device_details(devices: list, device_manager: DeviceManager):
    """Render detailed view for selected device"""
    st.markdown("### 🔍 Device Details")
    
    # Device selector
    device_names = [f"{d['name']} ({d['id']})" for d in devices]
    selected_device_name = st.selectbox("Select Device:", device_names)
    
    if selected_device_name:
        selected_idx = device_names.index(selected_device_name)
        device = devices[selected_idx]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Historical performance
            st.markdown("#### 📊 Historical Performance (Last 7 Days)")
            
            hist_data = device_manager.generate_historical_data(device['id'], 7)
            
            # Create subplots for historical data
            fig_hist = make_subplots(
                rows=2, cols=2,
                subplot_titles=('CPU Usage', 'Memory Usage', 'Accounts Created', 'Error Count'),
                specs=[[{"secondary_y": False}, {"secondary_y": False}],
                       [{"secondary_y": False}, {"secondary_y": False}]]
            )
            
            # Resample to daily averages for cleaner visualization
            daily_data = hist_data.set_index('timestamp').resample('D').mean()
            
            fig_hist.add_trace(
                go.Scatter(x=daily_data.index, y=daily_data['cpu_usage'],
                          mode='lines+markers', name='CPU %'),
                row=1, col=1
            )
            
            fig_hist.add_trace(
                go.Scatter(x=daily_data.index, y=daily_data['memory_usage'],
                          mode='lines+markers', name='Memory %'),
                row=1, col=2
            )
            
            fig_hist.add_trace(
                go.Scatter(x=daily_data.index, y=daily_data['accounts_created'],
                          mode='lines+markers', name='Accounts'),
                row=2, col=1
            )
            
            fig_hist.add_trace(
                go.Scatter(x=daily_data.index, y=daily_data['errors'],
                          mode='lines+markers', name='Errors'),
                row=2, col=2
            )
            
            fig_hist.update_layout(height=500, showlegend=False)
            st.plotly_chart(fig_hist, use_container_width=True)
        
        with col2:
            # Device specifications and status
            st.markdown("#### ⚙️ Device Specifications")
            
            spec_data = {
                'Property': [
                    'Device ID', 'Status', 'Health Score', 'Location', 'IP Address',
                    'Uptime', 'Success Rate (24h)', 'Errors Today', 'Last Seen'
                ],
                'Value': [
                    device['id'],
                    device['status'].title(),
                    f"{device['health_score']:.0f}%",
                    device['location'],
                    device['ip_address'],
                    f"{device['uptime_hours']} hours",
                    f"{device['success_rate_24h']:.1f}%",
                    device['errors_today'],
                    device['last_seen'].strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            
            spec_df = pd.DataFrame(spec_data)
            st.dataframe(spec_df, hide_index=True, use_container_width=True)
            
            # Quick actions
            st.markdown("#### ⚡ Quick Actions")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔄 Restart Device", key=f"restart_{device['id']}"):
                    st.success(f"Restart command sent to {device['name']}")
            with col_b:
                if st.button("⚠️ Maintenance Mode", key=f"maintenance_{device['id']}"):
                    st.warning(f"{device['name']} set to maintenance mode")
            
            if st.button("📋 Export Device Log", key=f"export_{device['id']}"):
                log_data = hist_data.to_csv(index=False)
                st.download_button(
                    label="📥 Download Log CSV",
                    data=log_data,
                    file_name=f"{device['id']}_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    key=f"download_{device['id']}"
                )

def render_alerts_section(devices: list):
    """Render alerts and notifications"""
    st.markdown("### 🚨 Alerts & Notifications")
    
    alerts = []
    
    # Generate alerts based on device conditions
    for device in devices:
        if device['status'] == 'error':
            alerts.append({
                'level': 'error',
                'device': device['name'],
                'message': f"Device {device['name']} is in error state",
                'timestamp': datetime.now() - timedelta(minutes=random.randint(5, 60))
            })
        
        if device['cpu_usage'] > 90:
            alerts.append({
                'level': 'warning',
                'device': device['name'],
                'message': f"High CPU usage: {device['cpu_usage']:.0f}%",
                'timestamp': datetime.now() - timedelta(minutes=random.randint(1, 30))
            })
        
        if device['memory_usage'] > 90:
            alerts.append({
                'level': 'warning',
                'device': device['name'],
                'message': f"High memory usage: {device['memory_usage']:.0f}%",
                'timestamp': datetime.now() - timedelta(minutes=random.randint(1, 30))
            })
        
        if device['health_score'] < 40:
            alerts.append({
                'level': 'critical',
                'device': device['name'],
                'message': f"Poor device health: {device['health_score']:.0f}%",
                'timestamp': datetime.now() - timedelta(minutes=random.randint(10, 120))
            })
    
    # Sort alerts by timestamp (newest first)
    alerts.sort(key=lambda x: x['timestamp'], reverse=True)
    
    if alerts:
        for alert in alerts[:10]:  # Show latest 10 alerts
            alert_color = {
                'error': 'error',
                'critical': 'error', 
                'warning': 'warning',
                'info': 'info'
            }.get(alert['level'], 'info')
            
            with st.container():
                if alert_color == 'error':
                    st.error(f"**{alert['device']}**: {alert['message']} - {alert['timestamp'].strftime('%H:%M:%S')}")
                elif alert_color == 'warning':
                    st.warning(f"**{alert['device']}**: {alert['message']} - {alert['timestamp'].strftime('%H:%M:%S')}")
                else:
                    st.info(f"**{alert['device']}**: {alert['message']} - {alert['timestamp'].strftime('%H:%M:%S')}")
    else:
        st.success("✅ No active alerts. All devices are operating normally.")

def main():
    """Main device status page function"""
    st.title("🖥️ Device Status & Monitoring")
    st.markdown("Real-time monitoring and management of account creation devices")
    
    # Initialize device manager
    device_manager = DeviceManager()
    
    # Generate device data
    with st.spinner("Loading device data..."):
        devices = device_manager.generate_device_data(8)
    
    # Auto-refresh checkbox
    auto_refresh = st.sidebar.checkbox("🔄 Auto Refresh (30s)", value=False)
    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()
    
    # Manual refresh button
    if st.sidebar.button("🔄 Refresh Now"):
        st.rerun()
    
    # Filter options
    st.sidebar.markdown("### 🔍 Filters")
    status_filter = st.sidebar.multiselect(
        "Device Status:",
        ["active", "idle", "maintenance", "error"],
        default=["active", "idle", "maintenance", "error"]
    )
    
    min_health = st.sidebar.slider("Min Health Score:", 0, 100, 0, 5)
    
    # Apply filters
    filtered_devices = [
        d for d in devices 
        if d['status'] in status_filter and d['health_score'] >= min_health
    ]
    
    # Render sections
    render_device_overview(filtered_devices)
    
    st.markdown("---")
    
    render_device_status_grid(filtered_devices)
    
    st.markdown("---")
    
    render_performance_analytics(filtered_devices)
    
    st.markdown("---")
    
    render_device_details(filtered_devices, device_manager)
    
    st.markdown("---")
    
    render_alerts_section(filtered_devices)
    
    # Export all device data
    st.markdown("---")
    st.markdown("### 📥 Export Device Data")
    
    if st.button("📊 Export All Device Data"):
        device_df = pd.DataFrame(filtered_devices)
        csv_data = device_df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv_data,
            file_name=f"device_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main() 