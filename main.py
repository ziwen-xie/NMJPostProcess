import numpy
import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv('W7_3_ROI2_job1.csv')
df.info()

job1 = df['Frame'].to_numpy
print(job1)

df2 = pd.read_csv('W7_3_ROI2_job3.csv')

