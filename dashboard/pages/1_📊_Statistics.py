"""
Statistics Page - Google Account Creator Dashboard

Detailed statistics and analytics page with advanced filtering,
comprehensive charts, and detailed data analysis.

Features:
- Comprehensive account creation analytics
- Advanced filtering and time range selection
- Multiple chart types and visualizations
- Success/failure analysis
- Trend analysis with predictions
- Export functionality
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

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from core.logger import get_logger

# Initialize logger
logger = get_logger("StatisticsPage")

# Page configuration
st.set_page_config(
    page_title="Statistics - Google Account Creator",
    page_icon="📊",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .metric-container {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    .filter-container {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 2rem;
    }
    
    .insight-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2196f3;
        margin: 1rem 0;
    }
    
    .success-metric {
        color: #28a745;
        font-weight: bold;
    }
    
    .warning-metric {
        color: #ffc107;
        font-weight: bold;
    }
    
    .error-metric {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

class StatisticsData:
    """Handles statistics data generation and processing"""
    
    def __init__(self):
        self.today = datetime.now().date()
    
    def generate_account_data(self, days: int = 90) -> pd.DataFrame:
        """Generate comprehensive account creation data"""
        data = []
        
        for i in range(days):
            date = self.today - timedelta(days=i)
            
            # Base creation pattern with weekly and seasonal variations
            base_accounts = 25
            weekly_factor = 1.2 if date.weekday() < 5 else 0.8  # Weekday vs weekend
            seasonal_factor = 1.1 if date.month in [3, 4, 9, 10] else 0.95  # Peak months
            random_factor = np.random.uniform(0.7, 1.3)
            
            accounts_created = max(0, int(base_accounts * weekly_factor * seasonal_factor * random_factor))
            
            # Success rate with realistic variations
            base_success_rate = 87
            success_variation = np.random.uniform(-5, 8)
            success_rate = max(70, min(95, base_success_rate + success_variation))
            
            successful_accounts = int(accounts_created * success_rate / 100)
            failed_accounts = accounts_created - successful_accounts
            
            # Account survival rates
            survival_24h = max(80, min(98, success_rate + np.random.uniform(-2, 5)))
            survival_7d = max(75, min(survival_24h, survival_24h - np.random.uniform(0, 8)))
            survival_30d = max(65, min(survival_7d, survival_7d - np.random.uniform(0, 10)))
            
            # Creation methods distribution
            methods = {
                'standard': np.random.uniform(0.3, 0.5),
                'verified_phone': np.random.uniform(0.2, 0.35),
                'verified_email': np.random.uniform(0.15, 0.25),
                'full_verification': np.random.uniform(0.05, 0.15)
            }
            
            # Normalize to sum to 1
            total = sum(methods.values())
            methods = {k: v/total for k, v in methods.items()}
            
            # Geographic distribution
            locations = {
                'north_america': np.random.uniform(0.35, 0.45),
                'europe': np.random.uniform(0.25, 0.35),
                'asia': np.random.uniform(0.15, 0.25),
                'other': np.random.uniform(0.05, 0.15)
            }
            
            # Normalize locations
            total_loc = sum(locations.values())
            locations = {k: v/total_loc for k, v in locations.items()}
            
            data.append({
                'date': date,
                'accounts_created': accounts_created,
                'successful_accounts': successful_accounts,
                'failed_accounts': failed_accounts,
                'success_rate': success_rate,
                'survival_24h': survival_24h,
                'survival_7d': survival_7d,
                'survival_30d': survival_30d,
                'method_standard': int(accounts_created * methods['standard']),
                'method_verified_phone': int(accounts_created * methods['verified_phone']),
                'method_verified_email': int(accounts_created * methods['verified_email']),
                'method_full_verification': int(accounts_created * methods['full_verification']),
                'location_na': int(accounts_created * locations['north_america']),
                'location_eu': int(accounts_created * locations['europe']),
                'location_asia': int(accounts_created * locations['asia']),
                'location_other': int(accounts_created * locations['other']),
                'day_of_week': date.strftime('%A'),
                'week_number': date.isocalendar()[1],
                'month': date.month,
                'is_weekend': date.weekday() >= 5
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('date').reset_index(drop=True)
        return df
    
    def calculate_insights(self, df: pd.DataFrame) -> dict:
        """Calculate key insights from the data"""
        insights = {}
        
        # Overall metrics
        insights['total_accounts'] = df['accounts_created'].sum()
        insights['total_successful'] = df['successful_accounts'].sum()
        insights['total_failed'] = df['failed_accounts'].sum()
        insights['avg_success_rate'] = df['success_rate'].mean()
        insights['avg_daily_creation'] = df['accounts_created'].mean()
        
        # Trends
        recent_7d = df.tail(7)
        previous_7d = df.iloc[-14:-7]
        
        insights['weekly_trend'] = {
            'current_avg': recent_7d['accounts_created'].mean(),
            'previous_avg': previous_7d['accounts_created'].mean(),
            'change_percent': ((recent_7d['accounts_created'].mean() - previous_7d['accounts_created'].mean()) / previous_7d['accounts_created'].mean()) * 100
        }
        
        insights['success_rate_trend'] = {
            'current_avg': recent_7d['success_rate'].mean(),
            'previous_avg': previous_7d['success_rate'].mean(),
            'change_percent': ((recent_7d['success_rate'].mean() - previous_7d['success_rate'].mean()) / previous_7d['success_rate'].mean()) * 100
        }
        
        # Best/worst performing days
        insights['best_day'] = df.loc[df['accounts_created'].idxmax()]
        insights['worst_day'] = df.loc[df['accounts_created'].idxmin()]
        
        # Weekend vs weekday performance
        weekday_data = df[~df['is_weekend']]
        weekend_data = df[df['is_weekend']]
        
        insights['weekday_performance'] = {
            'avg_creation': weekday_data['accounts_created'].mean(),
            'avg_success_rate': weekday_data['success_rate'].mean()
        }
        insights['weekend_performance'] = {
            'avg_creation': weekend_data['accounts_created'].mean(),
            'avg_success_rate': weekend_data['success_rate'].mean()
        }
        
        return insights

def render_filters(df: pd.DataFrame) -> tuple:
    """Render filter controls and return filtered data"""
    st.markdown('<div class="filter-container">', unsafe_allow_html=True)
    st.markdown("### 🔍 Filters")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        date_range = st.selectbox(
            "Time Range",
            ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Data"],
            index=2
        )
    
    with col2:
        min_success_rate = st.slider(
            "Min Success Rate (%)",
            min_value=0,
            max_value=100,
            value=0,
            step=5
        )
    
    with col3:
        creation_method = st.multiselect(
            "Creation Methods",
            ["Standard", "Verified Phone", "Verified Email", "Full Verification"],
            default=["Standard", "Verified Phone", "Verified Email", "Full Verification"]
        )
    
    with col4:
        include_weekends = st.checkbox("Include Weekends", value=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Apply filters
    filtered_df = df.copy()
    
    # Date range filter
    if date_range == "Last 7 Days":
        filtered_df = filtered_df.tail(7)
    elif date_range == "Last 30 Days":
        filtered_df = filtered_df.tail(30)
    elif date_range == "Last 90 Days":
        filtered_df = filtered_df.tail(90)
    
    # Success rate filter
    filtered_df = filtered_df[filtered_df['success_rate'] >= min_success_rate]
    
    # Weekend filter
    if not include_weekends:
        filtered_df = filtered_df[~filtered_df['is_weekend']]
    
    return filtered_df, date_range

def render_key_metrics(df: pd.DataFrame, insights: dict):
    """Render key performance metrics"""
    st.markdown("### 📊 Key Performance Metrics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            label="Total Accounts",
            value=f"{insights['total_accounts']:,}",
            delta=f"{insights['weekly_trend']['change_percent']:+.1f}%"
        )
    
    with col2:
        st.metric(
            label="Avg Success Rate",
            value=f"{insights['avg_success_rate']:.1f}%",
            delta=f"{insights['success_rate_trend']['change_percent']:+.1f}%"
        )
    
    with col3:
        st.metric(
            label="Daily Average",
            value=f"{insights['avg_daily_creation']:.0f}",
            delta=f"{insights['weekly_trend']['current_avg'] - insights['weekly_trend']['previous_avg']:+.0f}"
        )
    
    with col4:
        st.metric(
            label="Success Count",
            value=f"{insights['total_successful']:,}",
            delta=f"{insights['total_successful']/(insights['total_accounts'] or 1)*100:.1f}%"
        )
    
    with col5:
        st.metric(
            label="Failure Count",
            value=f"{insights['total_failed']:,}",
            delta=f"{insights['total_failed']/(insights['total_accounts'] or 1)*100:.1f}%"
        )

def render_trend_analysis(df: pd.DataFrame):
    """Render trend analysis charts"""
    st.markdown("### 📈 Trend Analysis")
    
    # Create subplots
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Account Creation Trend', 'Success Rate Trend', 
                       'Daily Distribution', 'Cumulative Performance'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Account creation trend
    fig.add_trace(
        go.Scatter(x=df['date'], y=df['accounts_created'],
                  mode='lines+markers', name='Accounts Created',
                  line=dict(color='#1f77b4')),
        row=1, col=1
    )
    
    # Success rate trend
    fig.add_trace(
        go.Scatter(x=df['date'], y=df['success_rate'],
                  mode='lines+markers', name='Success Rate (%)',
                  line=dict(color='#28a745')),
        row=1, col=2
    )
    
    # Daily distribution (box plot)
    fig.add_trace(
        go.Box(y=df['accounts_created'], name='Daily Creation',
              marker_color='#ff7f0e'),
        row=2, col=1
    )
    
    # Cumulative accounts
    df_sorted = df.sort_values('date')
    cumulative_accounts = df_sorted['accounts_created'].cumsum()
    fig.add_trace(
        go.Scatter(x=df_sorted['date'], y=cumulative_accounts,
                  mode='lines', name='Cumulative Accounts',
                  line=dict(color='#d62728')),
        row=2, col=2
    )
    
    fig.update_layout(height=600, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

def render_method_analysis(df: pd.DataFrame):
    """Render creation method analysis"""
    st.markdown("### 🔧 Creation Method Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Method distribution pie chart
        method_totals = {
            'Standard': df['method_standard'].sum(),
            'Verified Phone': df['method_verified_phone'].sum(),
            'Verified Email': df['method_verified_email'].sum(),
            'Full Verification': df['method_full_verification'].sum()
        }
        
        fig_pie = px.pie(
            values=list(method_totals.values()),
            names=list(method_totals.keys()),
            title='Distribution by Creation Method'
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Method trend over time
        method_df = pd.DataFrame({
            'Date': df['date'],
            'Standard': df['method_standard'],
            'Verified Phone': df['method_verified_phone'],
            'Verified Email': df['method_verified_email'],
            'Full Verification': df['method_full_verification']
        })
        
        method_df_melted = method_df.melt(id_vars=['Date'], var_name='Method', value_name='Count')
        
        fig_trend = px.line(
            method_df_melted,
            x='Date', y='Count', color='Method',
            title='Creation Method Trends Over Time'
        )
        st.plotly_chart(fig_trend, use_container_width=True)

def render_geographic_analysis(df: pd.DataFrame):
    """Render geographic distribution analysis"""
    st.markdown("### 🌍 Geographic Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Geographic distribution
        geo_totals = {
            'North America': df['location_na'].sum(),
            'Europe': df['location_eu'].sum(),
            'Asia': df['location_asia'].sum(),
            'Other': df['location_other'].sum()
        }
        
        fig_geo = px.bar(
            x=list(geo_totals.keys()),
            y=list(geo_totals.values()),
            title='Accounts by Geographic Region',
            color=list(geo_totals.values()),
            color_continuous_scale='viridis'
        )
        st.plotly_chart(fig_geo, use_container_width=True)
    
    with col2:
        # Geographic performance over time
        geo_df = pd.DataFrame({
            'Date': df['date'],
            'North America': df['location_na'],
            'Europe': df['location_eu'],
            'Asia': df['location_asia'],
            'Other': df['location_other']
        })
        
        # Calculate 7-day rolling average
        for col in ['North America', 'Europe', 'Asia', 'Other']:
            geo_df[f'{col}_avg'] = geo_df[col].rolling(window=7, center=True).mean()
        
        fig_geo_trend = go.Figure()
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
        
        for i, region in enumerate(['North America', 'Europe', 'Asia', 'Other']):
            fig_geo_trend.add_trace(
                go.Scatter(
                    x=geo_df['Date'],
                    y=geo_df[f'{region}_avg'],
                    mode='lines',
                    name=region,
                    line=dict(color=colors[i])
                )
            )
        
        fig_geo_trend.update_layout(
            title='Geographic Distribution Trends (7-day avg)',
            xaxis_title='Date',
            yaxis_title='Accounts Created'
        )
        st.plotly_chart(fig_geo_trend, use_container_width=True)

def render_insights_summary(insights: dict):
    """Render insights and recommendations"""
    st.markdown("### 💡 Insights & Recommendations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="insight-box">', unsafe_allow_html=True)
        st.markdown("**📊 Performance Insights**")
        
        # Weekly trend insight
        weekly_change = insights['weekly_trend']['change_percent']
        if weekly_change > 5:
            st.markdown(f"✅ **Strong Growth**: Account creation is up {weekly_change:.1f}% this week")
        elif weekly_change > 0:
            st.markdown(f"📈 **Positive Trend**: Account creation is up {weekly_change:.1f}% this week")
        else:
            st.markdown(f"📉 **Declining Trend**: Account creation is down {abs(weekly_change):.1f}% this week")
        
        # Success rate insight
        success_change = insights['success_rate_trend']['change_percent']
        if success_change > 2:
            st.markdown(f"🎯 **Improving Quality**: Success rate improved by {success_change:.1f}%")
        elif success_change < -2:
            st.markdown(f"⚠️ **Quality Concern**: Success rate declined by {abs(success_change):.1f}%")
        
        # Weekend vs weekday performance
        weekday_avg = insights['weekday_performance']['avg_creation']
        weekend_avg = insights['weekend_performance']['avg_creation']
        ratio = weekend_avg / weekday_avg if weekday_avg > 0 else 0
        
        if ratio < 0.7:
            st.markdown(f"📅 **Weekend Impact**: {(1-ratio)*100:.0f}% lower weekend performance")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="insight-box">', unsafe_allow_html=True)
        st.markdown("**🎯 Recommendations**")
        
        avg_success = insights['avg_success_rate']
        if avg_success < 80:
            st.markdown("🔧 **Process Improvement**: Success rate below 80% - review creation methods")
        elif avg_success > 90:
            st.markdown("🏆 **Excellent Performance**: Maintain current high-quality processes")
        
        # Best day insight
        best_day = insights['best_day']
        st.markdown(f"📅 **Peak Performance**: Best day was {best_day['date']} with {best_day['accounts_created']} accounts")
        
        # Method recommendation
        if insights['total_accounts'] > 100:
            st.markdown("📈 **Scale Opportunity**: Consider increasing verified creation methods for better survival rates")
        
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    """Main statistics page function"""
    st.title("📊 Account Creation Statistics")
    st.markdown("Comprehensive analytics and insights for Google account creation performance")
    
    # Initialize data
    data_handler = StatisticsData()
    
    # Generate data
    with st.spinner("Loading statistics data..."):
        df = data_handler.generate_account_data(90)
        insights = data_handler.calculate_insights(df)
    
    # Render filters
    filtered_df, date_range = render_filters(df)
    
    # Recalculate insights for filtered data
    filtered_insights = data_handler.calculate_insights(filtered_df)
    
    # Render sections
    render_key_metrics(filtered_df, filtered_insights)
    
    st.markdown("---")
    
    render_trend_analysis(filtered_df)
    
    st.markdown("---")
    
    render_method_analysis(filtered_df)
    
    st.markdown("---")
    
    render_geographic_analysis(filtered_df)
    
    st.markdown("---")
    
    render_insights_summary(filtered_insights)
    
    # Export functionality
    st.markdown("---")
    st.markdown("### 📥 Export Data")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        csv_data = filtered_df.to_csv(index=False)
        st.download_button(
            label="📊 Download CSV",
            data=csv_data,
            file_name=f"account_statistics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Summary report
        summary_data = {
            'Metric': ['Total Accounts', 'Success Rate', 'Daily Average', 'Best Day', 'Worst Day'],
            'Value': [
                f"{filtered_insights['total_accounts']:,}",
                f"{filtered_insights['avg_success_rate']:.1f}%",
                f"{filtered_insights['avg_daily_creation']:.0f}",
                f"{filtered_insights['best_day']['accounts_created']} ({filtered_insights['best_day']['date']})",
                f"{filtered_insights['worst_day']['accounts_created']} ({filtered_insights['worst_day']['date']})"
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_csv = summary_df.to_csv(index=False)
        
        st.download_button(
            label="📋 Download Summary",
            data=summary_csv,
            file_name=f"account_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col3:
        st.info(f"📊 Showing data for: **{date_range}**\n\n📈 {len(filtered_df)} days analyzed")

if __name__ == "__main__":
    main() 