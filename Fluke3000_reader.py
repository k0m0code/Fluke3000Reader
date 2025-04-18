#   Authors: Christian Komo, Niels Bidault
#   If given NotImplementedError and module ID 64 not found, enter 'mode COM3' in command line
#   If not, go to fluke3000.py, in line 229 change range to (2,7), run main, and change back to (1,7) and run main again


#   ToDo: Fix NotImplementedEra and module ID 64 bug
#   Todo: double check any code from AI and for matplotlib that's redundant (ex. update_scroll func, is fig.canvas.draw_idle() needed?) useful for optimizing program's memory and speed
#   Todo: Add error handling
#   Todo: Don't hard code, use constants instead
#   Todo: graph scrolling too laggy right now\
#   Todo: when you use zoom in feature, after a few sec it should also go back to following scroll bar at regular size
#   Todo: if timeout or serial connection, try have python script reset the port again automatically
#   Todo: When mouse hovers above the plotted line should return a data point
#   Moving average
#   Remove redundant timecnt value
#   Make timestamp and data of csv and chart be consistent
import instruments as ik
import re
from itertools import count
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.ticker import MaxNLocator
from matplotlib.widgets import Slider
import threading
import datetime
import csv

CsvWrite = False    # Csv file writing on/off

INTERVAL = 30       # Amount of seconds you want in interval window (multiplied by 2)
DELAY = 1000        # Number of milliseconds between measurements
BAUD = 115200
SCROLL_HOLD = 5
PORT = "\\\\.\\COM3"

FILENAME = "voltage_data-" + datetime.datetime.now().strftime('%Y-%m-%d') + "_" + datetime.datetime.now().strftime('%H_%M_%S') +".csv"
xval = []
yval = []
timeval = []
for i in range(INTERVAL):
    timeval.append(" ")
timesec = count()
timecnt = 0
scroll_status = False

def pointFollow():
    global scroll_status
    scroll_status = False

# Replace xaxis values with timestamps  
def add_time_labels(ax, timeval):
    xLabels = ax.get_xticks().tolist()
    newLabels = []
    for i in xLabels:
        newLabels.append(timeval[int(i)])    
    ax.set_xticklabels(newLabels,rotation=45,ha='right')

# Connect to the device's serial port, create plot and axes
mult = ik.fluke.Fluke3000.open_serial(PORT, BAUD)
fig, ax = plt.subplots()
plt.gca().xaxis.set_major_locator(MaxNLocator(integer=True))

# Function to write data to csv file with timestamps
def CsvWriteData(name, data, time):
    with open(name, 'a', newline='') as csvfile:
        csvwriter = csv.writer(csvfile)
        if csvfile.tell() == 0:
            csvwriter.writerow(['Time', 'Voltage'])
        now = datetime.datetime.now()
        dateStamp = now.strftime('%Y-%m-%d') + " " + time
        csvwriter.writerow([dateStamp, data])

# Animation function for graph. Updates graph and csv file with new voltage readings when called
def animate(i):
    global timecnt
    volt = ''
    timecnt = next(timesec)
    xval.append(timecnt)
    time = datetime.datetime.now().time().strftime("%H:%M:%S.%f")[:-4]
    timeval.insert(len(timeval)-INTERVAL,datetime.datetime.now().time().strftime("%H:%M:%S.%f")[:-4])
    
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
        CsvWriteData(FILENAME, str(volt), time)

    # Plot and update the new values onto the plot
    plt.subplots_adjust(bottom=0.25)
    plt.plot(xval,yval, color = 'blue')
    if (scroll_status != True) and (len(yval) > INTERVAL):
        ax.set_xlim(xval[len(xval)-1] - (INTERVAL*0.8), xval[len(xval)-1]+(INTERVAL*0.2))
    add_time_labels(ax, timeval)
    
# Create scroll bar
scrollax = plt.axes([0.1,0.02,0.8,0.06], facecolor = 'lightgoldenrodyellow')
scrollbar = Slider(scrollax, 'scroll', 0, 100, valinit = 0, valstep=1)
scrollTimer = threading.Timer(SCROLL_HOLD, pointFollow)

# Update and scroll through the graph display
def update_scroll(val):
    global scrollTimer
    global scroll_status
    scroll_status = True
    if scrollTimer.is_alive():
        scrollTimer.cancel()
    scrollTimer = threading.Timer(SCROLL_HOLD, pointFollow)
    scrollTimer.start()
    pos = scrollbar.val
    ax.set_xlim((pos/100)*timecnt, ((pos/100)*timecnt) + INTERVAL)
    add_time_labels(ax, timeval)
    fig.canvas.draw_idle()

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
