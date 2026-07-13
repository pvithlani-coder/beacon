import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import boto3
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aws_regions import get_primary_region

load_dotenv()

AWS_REGION = get_primary_region()
CHARTS_DIR = 'charts'


def ensure_charts_dir():
    if not os.path.exists(CHARTS_DIR):
        os.makedirs(CHARTS_DIR)


def get_daily_spend_data(days=30):
    client = boto3.client('ce', region_name=AWS_REGION)
    today = datetime.today()
    end = today.strftime('%Y-%m-%d')
    start = (today - timedelta(days=days)).strftime('%Y-%m-%d')

    response = client.get_cost_and_usage(
        TimePeriod={'Start': start, 'End': end},
        Granularity='DAILY',
        Metrics=['UnblendedCost']
    )

    dates = []
    amounts = []
    for day in response['ResultsByTime']:
        date = datetime.strptime(day['TimePeriod']['Start'], '%Y-%m-%d')
        amount = float(day['Total']['UnblendedCost']['Amount'])
        dates.append(date)
        amounts.append(round(amount, 4))

    return dates, amounts


def generate_cost_trend_chart(days=30):
    ensure_charts_dir()

    dates, amounts = get_daily_spend_data(days)

    if not dates:
        return None

    # Calculate trend
    avg = sum(amounts) / len(amounts)
    total = sum(amounts)

    # Color based on trend
    recent_avg = sum(amounts[-7:]) / 7 if len(amounts) >= 7 else avg
    prior_avg = sum(amounts[-14:-7]) / 7 if len(amounts) >= 14 else avg
    trend_up = recent_avg > prior_avg * 1.05

    # Set up the plot
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor('#0B1628')
    ax.set_facecolor('#112040')

    # Plot the line
    color = '#EF4444' if trend_up else '#10B981'
    ax.plot(dates, amounts, color=color, linewidth=2, zorder=3)
    ax.fill_between(dates, amounts, alpha=0.15, color=color, zorder=2)

    # Add average line
    ax.axhline(y=avg, color='#2563EB', linestyle='--',
               linewidth=1, alpha=0.7, label=f'Avg ${avg:.4f}/day')

    # Highlight max point
    max_idx = amounts.index(max(amounts))
    ax.scatter([dates[max_idx]], [amounts[max_idx]],
               color='#F59E0B', s=80, zorder=4)

    # Styling
    ax.set_xlabel('', color='#94A3B8')
    ax.set_ylabel('Daily Spend ($)', color='#94A3B8', fontsize=10)
    ax.tick_params(colors='#94A3B8', labelsize=8)
    ax.spines['bottom'].set_color('#1B3A6B')
    ax.spines['left'].set_color('#1B3A6B')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    plt.xticks(rotation=45, ha='right')

    # Grid
    ax.grid(True, color='#1B3A6B', linestyle='-', linewidth=0.5, alpha=0.5)

    # Title
    trend_text = "↑ Increasing" if trend_up else "↓ Decreasing"
    trend_color = '#EF4444' if trend_up else '#10B981'
    ax.set_title(
        f'OpsBeacon Cost Trend — Last {days} Days | Total: ${total:.2f} | {trend_text}',
        color='#F8FAFF', fontsize=11, fontweight='bold', pad=12
    )

    ax.legend(facecolor='#112040', edgecolor='#1B3A6B',
              labelcolor='#94A3B8', fontsize=8)

    plt.tight_layout()

    filepath = os.path.join(CHARTS_DIR, 'cost_trend.png')
    plt.savefig(filepath, dpi=150, bbox_inches='tight',
                facecolor='#0B1628', edgecolor='none')
    plt.close()

    print(f"Chart saved to {filepath}")
    return filepath


def generate_score_radar_chart(dimensions, title="OpsBeacon Score", overall=None):
    ensure_charts_dir()

    import numpy as np

    labels = list(dimensions.keys())
    values = list(dimensions.values())
    num_vars = len(labels)

    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    values_plot = values + [values[0]]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6),
                           subplot_kw=dict(polar=True))
    fig.patch.set_facecolor('#0B1628')
    ax.set_facecolor('#112040')

    ax.plot(angles, values_plot, color='#2563EB', linewidth=2)
    ax.fill(angles, values_plot, color='#2563EB', alpha=0.2)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color='#F8FAFF', fontsize=8)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20', '40', '60', '80', '100'],
                       color='#94A3B8', fontsize=7)
    ax.grid(color='#1B3A6B', linestyle='-', linewidth=0.5)
    ax.spines['polar'].set_color('#1B3A6B')

    if overall is None:
        overall = int(sum(values) / len(values))
    ax.set_title(f'{title}: {overall}/100',
                 color='#F8FAFF', fontsize=12,
                 fontweight='bold', pad=20)

    plt.tight_layout()

    filename = title.lower().replace(' ', '_').replace('/', '_')
    filepath = os.path.join(CHARTS_DIR, f'{filename}.png')
    plt.savefig(filepath, dpi=150, bbox_inches='tight',
                facecolor='#0B1628', edgecolor='none')
    plt.close()

    print(f"Chart saved to {filepath}")
    return filepath


if __name__ == "__main__":
    print("\n=== Chart Generator Test ===")

    print("\nGenerating cost trend chart...")
    path = generate_cost_trend_chart(days=30)
    print(f"Cost trend chart: {path}")

    print("\nGenerating score radar chart...")
    dimensions = {
        'Coverage': 25,
        'Tool Efficiency': 80,
        'Detection Quality': 60,
        'Asset Hygiene': 94,
        'Logging Economy': 100,
        'Compliance': 100,
        'Governance': 70
    }
    path = generate_score_radar_chart(dimensions, "Security Cost Score")
    print(f"Score chart: {path}")

    print("\nDone. Check the charts/ folder.")