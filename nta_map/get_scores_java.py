import pandas as pd
df = pd.read_csv('merge_datasets/bus_need_index.csv')
for _, row in df.iterrows():
    print(f"  '{row['NTACode']}': {row['Score']},")