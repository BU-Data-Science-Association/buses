import pandas as pd
import numpy as np
from scipy import stats
import seaborn as sns
import matplotlib.pyplot as plt

# Load data
election = pd.read_csv('nta_mayoral_results_2025_general.csv')
bus_need = pd.read_csv('merge_datasets/bus_need_index_final_full.csv')

# Compute alternate index WITHOUT car_score (renormalized weights)
W_INCOME      = 0.25
W_BUS_SUBWAY  = 0.20
W_RELIABILITY = 0.15
W_RIDERSHIP   = 0.20
total_w = W_INCOME + W_BUS_SUBWAY + W_RELIABILITY + W_RIDERSHIP  # 0.80

bus_need['index_no_car'] = (
    (W_INCOME / total_w)      * bus_need['income_score'].fillna(0) +
    (W_BUS_SUBWAY / total_w)  * bus_need['bus_subway_score'].fillna(0) +
    (W_RELIABILITY / total_w) * bus_need['reliability_score'].fillna(0) +
    (W_RIDERSHIP / total_w)   * bus_need['ridership_score'].fillna(0)
).round(6)

# Merge on NTA code
merged = election.merge(bus_need, left_on='nta2020', right_on='NTACode', how='inner')

# Variables of interest
index_vars = ['income_score', 'car_score', 'bus_subway_score',
              'reliability_score', 'ridership_score', 'index_score', 'index_no_car']
mamdani_col = 'Zohran Kwame Mamdani (%)'

# Keep only rows with complete data
cols_needed = index_vars + [mamdani_col]
df = merged.dropna(subset=cols_needed).copy()
print(f"NTAs with complete data: {len(df)} (out of {len(merged)} matched)")

# --- Pairwise correlations with Mamdani % ---
print("\n" + "=" * 70)
print("CORRELATION ANALYSIS: Mamdani Vote % vs Bus Need Index Components")
print("=" * 70)

results = []
for var in index_vars:
    r, p = stats.pearsonr(df[mamdani_col], df[var])
    results.append({'Variable': var, 'Pearson r': r, 'p-value': p})

results_df = pd.DataFrame(results)
results_df['Significant'] = results_df['p-value'].apply(
    lambda p: '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else ''
)

print(f"\n{'Variable':<25} {'Pearson r':>10} {'p-value':>12} {'Sig':>5}")
print("-" * 55)
for _, row in results_df.iterrows():
    print(f"{row['Variable']:<25} {row['Pearson r']:>10.4f} {row['p-value']:>12.2e} {row['Significant']:>5}")

print("\nSignificance: *** p<0.001, ** p<0.01, * p<0.05")

# Interpretation
print("\n" + "=" * 70)
print("INTERPRETATION")
print("=" * 70)
for _, row in results_df.iterrows():
    r = row['Pearson r']
    strength = 'strong' if abs(r) > 0.5 else 'moderate' if abs(r) > 0.3 else 'weak'
    direction = 'positive' if r > 0 else 'negative'
    sig = ' (statistically significant)' if row['Significant'] else ' (not significant)'
    print(f"  {row['Variable']}: {strength} {direction} correlation (r={r:.4f}){sig}")

# --- Full correlation matrix ---
corr_vars = [mamdani_col] + index_vars
labels = ['Mamdani %', 'Income', 'Car', 'Bus vs Subway',
          'Reliability', 'Ridership', 'Bus Need Index', 'Index (no Car)']

corr_matrix = df[corr_vars].corr()

# --- Heatmap ---
fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(
    corr_matrix,
    annot=True,
    fmt='.3f',
    cmap='RdBu_r',
    center=0,
    vmin=-1,
    vmax=1,
    xticklabels=labels,
    yticklabels=labels,
    square=True,
    linewidths=0.5,
    ax=ax
)
ax.set_title('Correlation Matrix: 2025 Mamdani Vote % vs Bus Need Index Components',
             fontsize=13, pad=15)
plt.tight_layout()
plt.savefig('election_correlation_heatmap.png', dpi=150, bbox_inches='tight')
print(f"\nHeatmap saved to election_correlation_heatmap.png")

# --- Export merged CSV ---
export_cols = ['nta2020', 'ntaname', 'boroname', 'Total Votes',
               'Zohran Kwame Mamdani', mamdani_col,
               'Andrew M. Cuomo (%)', 'Curtis A. Sliwa (%)',
               'winning_candidate', 'winning_percentage',
               'income_score', 'car_score', 'bus_subway_score',
               'reliability_score', 'ridership_score', 'index_score', 'index_no_car']
df[export_cols].sort_values('index_score', ascending=False).to_csv(
    'election_bus_need_merged.csv', index=False
)
print(f"Merged CSV saved to election_bus_need_merged.csv ({len(df)} NTAs)")

# --- Scatter plots ---
scatter_vars = ['index_score', 'index_no_car', 'income_score', 'car_score',
                'bus_subway_score', 'reliability_score', 'ridership_score']
scatter_labels = ['Bus Need Index', 'Index (no Car)', 'Income Score', 'Car Score',
                  'Bus vs Subway Score', 'Reliability Score', 'Ridership Score']

fig, axes = plt.subplots(2, 4, figsize=(20, 10))
axes = axes.flatten()

for i, (var, label) in enumerate(zip(scatter_vars, scatter_labels)):
    ax = axes[i]
    r, p = stats.pearsonr(df[mamdani_col], df[var])
    ax.scatter(df[var], df[mamdani_col], alpha=0.5, s=25, edgecolors='none')
    # regression line
    m, b = np.polyfit(df[var], df[mamdani_col], 1)
    x_line = np.linspace(df[var].min(), df[var].max(), 100)
    ax.plot(x_line, m * x_line + b, color='red', linewidth=1.5)
    ax.set_xlabel(label, fontsize=11)
    ax.set_ylabel('Mamdani %', fontsize=11)
    sig = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else 'ns'
    ax.set_title(f'{label}\nr = {r:.3f} ({sig})', fontsize=11)

# Hide unused subplot
axes[7].set_visible(False)

fig.suptitle('Mamdani Vote % vs Bus Need Index Components (n=174 NTAs)',
             fontsize=14, y=1.02)
plt.tight_layout()
plt.savefig('election_scatter_plots.png', dpi=150, bbox_inches='tight')
print("Scatter plots saved to election_scatter_plots.png")
