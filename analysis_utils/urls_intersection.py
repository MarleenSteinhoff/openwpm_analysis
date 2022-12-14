import pandas as pd



CSV1 = "top-1m-11-11-2016.csv"
CSV2 = "top-1m.csv"


df1 = pd.read_csv(CSV1, header=None).iloc[:,[1]]

df2 = pd.read_csv(CSV2, header=None).iloc[:,[1]]

int_df = pd.merge(df1, df2, how ='inner')
print(int_df)
print(int_df.tail)
int_df.to_csv('intersect.csv', index=False)

