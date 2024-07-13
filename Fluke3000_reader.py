#   Authors: Christian Komo, Niels Bidault
#   If given NotImplementedError and module ID 64 not found, enter 'mode COM3' in command line
#   If not, go to fluke3000.py, in line 229 change range to (2,7), run main, and change back to (1,7) and run main again


#   ToDo: Fix NotImplementedEra and module ID 64 bug
#   Todo: double check any code from AI and for matplotlib that's redundant (ex. update_scroll func, is fig.canvas.draw_idle() needed?) useful for optimizing program's memory and speed
#   Todo: Add error handling
#   Todo: Don't hard code, use constants instead
#   Todo: Increase interval indefinetely so user can scroll back and forth between all the data
#   Todo: Make the graph move along with the updating data if scroll bar is not in use
#   Todo: Add time stamp onto graph x axis?

import instruments as ik
import re
from itertools import count
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider
import matplotlib.dates as mdates
import datetime
import csv

CsvWrite = False    # Csv file writing on/off

INTERVAL = 20       # Amount of seconds you want in interval window (multiplied by 2)
DELAY = 500         # Number of milliseconds between measurements
BAUD = 115200
PORT = "\\\\.\\COM3"
FILENAME = "voltage_data-" + datetime.datetime.now().strftime('%Y-%m-%d') + "_" + datetime.datetime.now().strftime('%H_%M_%S') +".csv"
xval = []
yval = []
timeval = []
timesec = count()
timecnt = 0


# Connect to the device's serial port, create plot and axes
mult = ik.fluke.Fluke3000.open_serial(PORT, BAUD)
fig, ax = plt.subplots()

# Function to write data to csv file with timestamps
def CsvWriteData(name, data):
    with open(FILENAME, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        if csvfile.tell() == 0:
            csvwriter.writerow(['Date', 'Time', 'Voltage'])
        now = datetime.datetime.now()
        dateStamp = now.strftime('%Y-%m-%d')
        timeStamp = now.strftime('%H:%M:%S')
        csvwriter.writerow([dateStamp, timeStamp, data])

# Animation function for graph. Updates graph and csv file with new voltage readings when called
def animate(i):
    global timecnt
    volt = ''

    
    xval.append(timecnt)                        # Append time stamp data into xval list
    timeval.append(datetime.datetime.now().time().strftime("%H:%M:%S.%f")[:-4])
    timecnt = next(timesec)
    data = mult.measure(mult.Mode.voltage_dc)   # Measures the DC voltage

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
        CsvWriteData(FILENAME, str(volt))

    # Plot and update the new values onto the plot
    plt.subplots_adjust(bottom=0.25)
    plt.plot(xval,yval, color = 'blue')


# Create scroll bar
scrollax = plt.axes([0.1,0.02,0.8,0.06], facecolor = 'lightgoldenrodyellow')
scrollbar = Slider(scrollax, 'scroll', 0, 100, valinit = 0, valstep=1)

# Update and scroll through the graph display
def update_scroll(val):
    pos = scrollbar.val
    ax.set_xlim((pos/100)*timecnt, ((pos/100)*timecnt) + INTERVAL)
    fig.canvas.draw_idle()

    Labels = ax.get_xticks().tolist()
    newLabels = timeval[int(xLabels[0]):int((xLabels[len(xLabels) - 1]))]
    ax.set_xticklabels(newLabels,rotation=45,ha='right')

    # xlabels = ax.get_xticklabels()
    # newXLabels = [datetime.datetime for tick in xlabels]
    # ax.set_xticklabels(newXLabels,rotation=4,ha='right')

scrollbar.on_changed(update_scroll)                     # Scroll function
ax.set_xlim(0,INTERVAL)                                 # Initial window view with starting x values
plt.sca(ax)                                             # Set the main axes to animate line on
plt.tick_params(labelsize = 9)



ani = FuncAnimation(plt.gcf(), animate, interval=DELAY) # FuncAnimation object to update graph as time goes on
plt.tight_layout()                                      # Formatting
plt.show()

# Flush out the cache system
mult.reset()
mult.flush()