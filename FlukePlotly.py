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


from __future__ import print_function
from sys import stdout
from time import sleep
from daqhats import mcc128, OptionFlags, HatIDs, HatError, AnalogInputMode, \
    AnalogInputRange
from daqhats_utils import select_hat_device, enum_mask_to_string, \
    chan_list_to_mask, input_mode_to_string, input_range_to_string



ENABLE_DASH = True           # Enable/Disable Dash app
ENABLE_PROMETHEUS = True     # Enable/Disable Prometheus publishing
mcc128_source = True         # Source from MCC128

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
# mcc128 publishing
# =========================
READ_ALL_AVAILABLE = -1
CURSOR_BACK_2 = '\x1b[2D'
ERASE_TO_END_OF_LINE = '\x1b[0K'



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
def update_graph(n, mcc128_measurements):
    global pressure_list, last_publish_time, measurement_count
    # Acquire voltage data
    volt = ''
    xval.append(next(timesec))
    current_time = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-4]
    timeval.append(current_time)
    data = None
    if mcc128_measurements:
    

        read_result = hat.a_in_scan_read(read_request_size, timeout)

        # Check for an overrun error
        if read_result.hardware_overrun:
            print('\n\nHardware overrun\n')
            return False
        elif read_result.buffer_overrun:
            print('\n\nBuffer overrun\n')
            return False

        samples_read_per_channel = int(len(read_result.data) / num_channels)
        total_samples_read += samples_read_per_channel

        # Display the last sample for each channel.
        print('\r{:12}'.format(samples_read_per_channel),
              ' {:12} '.format(total_samples_read), end='')

        if samples_read_per_channel > 0:
            index = samples_read_per_channel * num_channels - num_channels

            for i in range(num_channels):
                print('{:10.5f}'.format(read_result.data[index+i]), 'V ',
                      end='')
            stdout.flush()

            sleep(0.1)

        data = read_and_display_data(hat, num_channels)
    else:
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
    return True
    # return figure1, figure2

# =========================
# Run the Dash App
# =========================
if __name__ == '__main__':
    if ENABLE_DASH:
        app.run_server(debug=True, use_reloader=False)
    else:
        # If Dash is disabled, continuously acquire data and publish to Prometheus
        if mcc128_source:
            channels = [0, 1, 2, 3]
            channel_mask = chan_list_to_mask(channels)
            num_channels = len(channels)
        
            input_mode = AnalogInputMode.SE
            input_range = AnalogInputRange.BIP_10V
        
            samples_per_channel = 0
        
            options = OptionFlags.CONTINUOUS
        
            scan_rate = 1000.0

            
            # Select an MCC 128 HAT device to use.
            address = select_hat_device(HatIDs.MCC_128)
            hat = mcc128(address)

            hat.a_in_mode_write(input_mode)
            hat.a_in_range_write(input_range)


            # Configure and start the scan.
            # Since the continuous option is being used, the samples_per_channel
            # parameter is ignored if the value is less than the default internal
            # buffer size (10000 * num_channels in this case). If a larger internal
            # buffer size is desired, set the value of this parameter accordingly.
            hat.a_in_scan_start(channel_mask, samples_per_channel, scan_rate,
                            options)
            total_samples_read = 0
            read_request_size = READ_ALL_AVAILABLE
            timeout = 5.0
            
            mcc128NoBug = True
        try:
            while True and mcc128NoBug:
                mcc128NoBug = update_graph(0, mcc128_source)
                time.sleep(DELAY)
        except KeyboardInterrupt:
            print("Data acquisition stopped.")

# =========================
# Cleanup
# =========================
mult.reset()
mult.flush()
