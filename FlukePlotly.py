#   Authors: Christian Komo, Niels Bidault
#   If given NotImplementedError and module ID 64 not found, enter 'mode COM3' in command line
#   If not, go to fluke3000.py, in line 229 change range to (2,7), run main, and change back to (1,7) and run main again


#   ToDo: Fix NotImplementedEra and module ID 64 bug
#   Todo: double check any code from AI and for matplotlib that's redundant (ex. update_scroll func, is fig.canvas.draw_idle() needed?) useful for optimizing program's memory and speed
#   Todo: Add error handling
#   Todo: Don't hard code, use constants instead
#   Todo: graph scrolling too laggy right now\
#   Todo: when you use zoom in feature, after a few sec it should also go back to following scroll bar at regular size
#   Todo: if timeout or serial connection, try have python script reset the port again
#   Todo: When mouse hovers above the plotted line should return a data point
#   Moving average
#   Remove redundant timecnt value
#   Make timestamp and data of csv and chart be consistent
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import numpy as np
import pandas as pd
import threading
import datetime
import csv
import instruments as ik
import re
from itertools import count
import random

CsvWrite = False    # Csv file writing on/off

INTERVAL = 100       # Amount of seconds you want in interval window (multiplied by 2)
DELAY = 1            # Number of seconds between measurements
BAUD = 115200
PORT = "\\\\.\\COM3"
FILENAME = "voltage_data-" + datetime.datetime.now().strftime('%Y-%m-%d') + "_" + datetime.datetime.now().strftime('%H_%M_%S') +".csv"
xval = []
yval = []
timeval = []
for i in range(INTERVAL):
    timeval.append(" ")
timesec = count()
timecnt = 0

mult = ik.fluke.Fluke3000.open_serial(PORT, BAUD)

def CsvWriteData(name, data, time):
    with open(name, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        if csvfile.tell() == 0:
            csvwriter.writerow(['Time', 'Voltage'])
        now = datetime.datetime.now()
        dateStamp = now.strftime('%Y-%m-%d') + " " + time
        csvwriter.writerow([dateStamp, data])










# Initialize the Dash app
app = dash.Dash(__name__)

# Layout of the Dash app
app.layout = html.Div([
    dcc.Graph(id='live-update-graph'),
    dcc.Interval(
        id='interval-component',
        interval=DELAY*1000,  # Update every 1 second
        n_intervals=0
    )
])

# Callback to update the graph
@app.callback(
    Output('live-update-graph', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_graph(n):
    global timecnt
    volt = ''
    timecnt = next(timesec)
    xval.append(timecnt)
    time = datetime.datetime.now().time().strftime("%H:%M:%S.%f")[:-4]
    timeval.insert(len(timeval) - INTERVAL, datetime.datetime.now().time().strftime("%H:%M:%S.%f")[:-4])

    data = mult.measure(mult.Mode.voltage_dc)  # Measures the DC voltage
    

    # Append voltage data into yval list
    if str(data) != '0.0 V':
        value = re.findall(r'-?\d+\.\d+', str(data))
        volt = value[0]
        yval.append(float(volt))
    else:
        volt = 0
        yval.append(volt)

    # Write to csv file if allowed
    if CsvWrite:
        CsvWriteData(FILENAME, str(volt), time)

    # Create the Plotly figure
    figure = {
        'data': [go.Scatter(x=xval, y=yval, mode='lines+markers')],
        'layout': go.Layout(
            title='Real-Time Updating Line Graph',
            xaxis=dict(title='Time'),
            yaxis=dict(title='Value'),
            xaxis_rangeslider=dict(visible=False),
            xaxis_range=[xval[0] if xval else datetime.datetime.now(), datetime.datetime.now()]
        )
    }
    
    return figure

# Run the Dash app
if __name__ == '__main__':
    app.run_server(debug=True, use_reloader = False)

# Flush out the cache system
mult.reset()
mult.flush()
print('done')
