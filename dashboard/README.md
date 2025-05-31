# Google Account Creator Dashboard

A comprehensive web-based dashboard for monitoring and managing the Google Account Creator system.

## Features

### 🎯 System Status Overview
- Real-time system health monitoring
- Service status indicators
- Active alerts and warnings
- System uptime tracking

### 📊 Account Statistics
- Total accounts created
- Daily creation trends
- Success rate analytics
- Active vs failed account ratios

### 📈 Visual Analytics
- Interactive charts and graphs
- Account creation trends over time
- Success rate visualization
- Survival rate analysis by different criteria

### 🖥️ Device Management
- Device status monitoring
- Performance metrics (CPU, Memory)
- Geographic distribution
- Creation statistics per device

### 📥 Data Export
- CSV export functionality
- Historical data download
- Custom time range selection

## Installation

### Prerequisites
- Python 3.8 or higher
- Required packages (see requirements.txt)

### Setup
1. Install required packages:
```bash
pip install -r dashboard/requirements.txt
```

2. Ensure the core modules are available (logger, database, config_manager)

## Usage

### Quick Start
Run the dashboard using the provided script:
```bash
python scripts/run_dashboard.py
```

### Advanced Usage
```bash
# Run on custom host and port
python scripts/run_dashboard.py --host 0.0.0.0 --port 8080

# Run in debug mode
python scripts/run_dashboard.py --debug
```

### Direct Streamlit Usage
```bash
streamlit run dashboard/main.py --server.port 8501
```

## Dashboard Sections

### Main Overview
- System health indicators
- Key performance metrics
- Recent alerts and notifications

### Quick Statistics
- Account creation summary
- Success rates
- Active account counts
- Failure analysis

### Charts and Analytics
- **Daily Account Creation**: Line chart showing account creation trends
- **Success Rate Trend**: Success rate changes over time
- **Survival Rates**: Account survival by time period and creation method
- **Performance Metrics**: System and device performance data

### Sidebar Controls
- **Auto Refresh**: Automatic data refresh every 30 seconds
- **Manual Refresh**: On-demand data refresh
- **Time Range Selection**: Filter data by time period
- **Data Export**: Download statistics as CSV

## Configuration

### Environment Variables
The dashboard reads configuration from the system's ConfigManager:
- API keys for AI services
- Database connection settings
- Logging configuration

### Data Sources
- **Real-time data**: System status, device metrics
- **Historical data**: Account statistics, creation trends
- **Sample data**: Used when database is unavailable

## Features in Detail

### System Status Monitoring
- Service health checks
- Database connectivity status
- Configuration validation
- Alert management

### Account Analytics
- Creation success rates
- Survival rate analysis
- Geographic distribution
- Time-based trends

### Device Performance
- CPU and memory usage
- Account creation capacity
- Geographic location tracking
- Last seen timestamps

### Data Visualization
- Interactive Plotly charts
- Responsive design
- Color-coded status indicators
- Real-time updates

## Troubleshooting

### Common Issues

1. **Dashboard won't start**
   - Check if required packages are installed
   - Verify Python version compatibility
   - Ensure port is not in use

2. **No data displayed**
   - Check database connection
   - Verify configuration files
   - Review log files for errors

3. **Charts not loading**
   - Ensure Plotly is properly installed
   - Check browser compatibility
   - Clear browser cache

### Debug Mode
Run with `--debug` flag for detailed error information:
```bash
python scripts/run_dashboard.py --debug
```

## Development

### Adding New Features
1. Create new functions in `dashboard/main.py`
2. Add corresponding data methods to `DashboardData` class
3. Update the main rendering function
4. Test with sample data

### Customization
- Modify CSS in the `st.markdown` section
- Adjust chart configurations in render functions
- Update color schemes and themes
- Add new metric calculations

## Security

### Access Control
- Basic authentication (planned)
- Session management
- Secure data handling

### Data Privacy
- Sensitive data masking
- Secure data transmission
- Log data protection

## Performance

### Optimization Features
- Efficient data queries
- Cached computations
- Minimal resource usage
- Responsive design

### Scalability
- Supports multiple concurrent users
- Efficient data processing
- Minimal server resources

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review log files in `logs/` directory
3. Ensure all dependencies are installed
4. Verify system configuration

## Future Enhancements

- [ ] User authentication system
- [ ] Advanced filtering options
- [ ] Custom dashboard layouts
- [ ] Mobile app companion
- [ ] API endpoints for external integration
- [ ] Advanced analytics and ML insights
- [ ] Automated report generation
- [ ] Multi-language support 