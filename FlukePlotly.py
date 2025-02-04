# Authors: Christian Komo, Niels Bidault
# 2025 Update adding Prometheus-client

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway
import plotly.graph_objs as go
import datetime
import csv
import instruments as ik
import re
from itertools import count
import numpy as np
from scipy.interpolate import interp1d
import time


ENABLE_DASH = True           # Enable/Disable Dash app
ENABLE_PROMETHEUS = True     # Enable/Disable Prometheus publishing

# Serial Port Settings
BAUD = 115200
PORT = "\\.\\COM6" # Check in Device Managers where the FLUKE usb bluetooth received is installed

# Prometheus Settings
PUSHGATEWAY_ADDRESS = 'localhost:9091'
registry = CollectorRegistry()
gauge_avg = Gauge('pressure_list', 'Average Reading from Voltmeter', registry=registry)
gauge_individual = Gauge('pressure_value', 'Individual Readings from Voltmeter', ['index'], registry=registry)
gauge_measurement_rate = Gauge('measurement_rate', 'Measurement Rate from Fluke Meter', registry=registry)  # New gauge for measurement rate

# Data Acquisition Settings
INTERVAL = 100
DELAY = 1
ROLLING_AVG_MEASURE = 10
PUBLISH_INTERVAL = 15  # Prometheus publishing rate (15 seconds)

CsvWrite = False
FILENAME = f"voltage_data-{datetime.datetime.now().strftime('%Y-%m-%d_%H_%M_%S')}.csv"

# =========================
# Data Structures
# =========================
xval = []
yval = []
yval_rolling = []
timeval = []
timesec = count()
pressure_list = []
last_publish_time = time.time()
measurement_count = 0  # Counter for measurements

# Multimeter Initialization
mult = ik.fluke.Fluke3000.open_serial(PORT, BAUD)

# =========================
# CSV Writing Function
# =========================
def CsvWriteData(name, data, time):
    with open(name, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        if csvfile.tell() == 0:
            csvwriter.writerow(['Time', 'Voltage'])
        now = datetime.datetime.now()
        dateStamp = now.strftime('%Y-%m-%d') + " " + time
        csvwriter.writerow([dateStamp, data])

# =========================
# Prometheus Publishing Function
# =========================
def publish_to_prometheus(voltage_list, measurement_rate):
    if not voltage_list:
        return

    avg_voltage = sum(voltage_list) / len(voltage_list)
    gauge_avg.set(avg_voltage)

    for idx, value in enumerate(voltage_list):
        gauge_individual.labels(index=idx).set(value)

    gauge_measurement_rate.set(measurement_rate)  # Publish measurement rate

    push_to_gateway(PUSHGATEWAY_ADDRESS, job='voltmeter', registry=registry)
    print(f"[Prometheus] Data Sent: Avg = {avg_voltage:.2f} V | Total Readings = {len(voltage_list)} | Measurement Rate = {measurement_rate:.2f} Hz")

# =========================
# Dash App Setup
# =========================
app = dash.Dash(__name__)
app.layout = html.Div([
    dcc.Graph(id='live-update-graph-1'),
    dcc.Graph(id='live-update-graph-2'),
    dcc.Interval(id='interval-component', interval=DELAY * 1000, n_intervals=0)
])

def create_interpolator():
    # Provided by VARIAN Ion Pump controller 921-0062
    voltage_mV = np.array([5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0,
                           55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 95.0])
    pressure_Torr = np.array([1e-8, 1.5e-8, 2.4e-8,
                              3.7e-8, 6.0e-8, 1.0e-7,
                              1.7e-7, 3.0e-7, 5.5e-7,
                              1.0e-6, 1.6e-6, 2.8e-6,
                              5.0e-6, 8.0e-6, 1.5e-5,
                              2.6e-5, 4.0e-5, 6.0e-5,
                              1.0e-4])

    # Interpolation with extrapolation for values below 5 mV
    interpolator = interp1d(voltage_mV, pressure_Torr, kind='cubic', fill_value='extrapolate')

    return interpolator

def get_pressure(voltage_mV, unit='Torr'):

    interpolator = create_interpolator()
    pressure_Torr = interpolator(voltage_mV)

    if unit == 'mbar':
        return pressure_Torr * 1.33322  # Conversion factor from Torr to mbar
    return pressure_Torr


# =========================
# Dash Callback for Updating Graphs
# =========================
@app.callback(
    [Output('live-update-graph-1', 'figure'),
     Output('live-update-graph-2', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_graph(n):
    global pressure_list, last_publish_time, measurement_count

    # Acquire voltage data
    volt = ''
    xval.append(next(timesec))
    current_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-4]
    timeval.append(current_time)

    data = mult.measure(mult.Mode.voltage_dc)

    # Process the data
    if str(data) != '0.0 V':
        value = re.findall(r'-?\d+\.\d+', str(data))
        volt = float(value[0])
    else:
        volt = 0

    yval.append(volt)
    pressure_list.append(get_pressure(volt * 1000, unit='Torr'))
    measurement_count += 1  # Increment measurement count
    print(f"Measured Voltage: {volt} V")

    # Rolling Average Calculation
    if len(yval) >= ROLLING_AVG_MEASURE:
        temp_avg = np.mean(yval[-ROLLING_AVG_MEASURE:])
        yval_rolling.append(temp_avg)

    # CSV Writing
    if CsvWrite:
        CsvWriteData(FILENAME, str(volt), current_time)

    # Prometheus Publishing Every 15 Seconds
    if ENABLE_PROMETHEUS and (time.time() - last_publish_time >= PUBLISH_INTERVAL):
        measurement_rate = measurement_count / PUBLISH_INTERVAL  # Calculate measurement rate
        publish_to_prometheus(pressure_list, measurement_rate)
        pressure_list = []  # Clear the list after publishing
        measurement_count = 0  # Reset measurement count
        last_publish_time = time.time()

    # Graph 1: Raw Voltage Readings
    figure1 = {
        'data': [go.Scatter(x=xval, y=yval, mode='lines+markers')],
        'layout': go.Layout(
            title='Fluke3000 FC Readings',
            xaxis=dict(title='Time (s)'),
            yaxis=dict(title='Voltage (V)'),
            xaxis_rangeslider=dict(visible=False)
        )
    }

    # Graph 2: Rolling Average
    figure2 = {
        'data': [go.Scatter(x=xval[:len(yval_rolling)], y=yval_rolling, mode='lines+markers')],
        'layout': go.Layout(
            title=f'Rolling Average of Last {ROLLING_AVG_MEASURE} Measurements',
            xaxis=dict(title='Time (s)'),
            yaxis=dict(title='Average Voltage (V)'),
            xaxis_rangeslider=dict(visible=False)
        )
    }

    return figure1, figure2

# =========================
# Run the Dash App
# =========================
if __name__ == '__main__':
    if ENABLE_DASH:
        app.run_server(debug=True, use_reloader=False)
    else:
        # If Dash is disabled, continuously acquire data and publish to Prometheus
        try:
            while True:
                update_graph(0)
                time.sleep(DELAY)
        except KeyboardInterrupt:
            print("Data acquisition stopped.")

# =========================
# Cleanup
# =========================
mult.reset()
mult.flush()
