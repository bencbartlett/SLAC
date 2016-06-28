#!/usr/local/bin/python

import MySQLdb
import datetime
import time
import readline
import os
import re
import sys
import ConfigParser


#****************************************************************************
#
#  Get command line parameters
#
#  initdir   The directory containing the initialization file
#
#  database  The database to use: "prod" or "test"
#
#  subsys    The subsystem to use, e.g. ccs-refrig-subscale
#
#  userinit  The body name (".ini" is appended) of an optional user
#            initialization file
#
#****************************************************************************

# Usage: python refrigPlot.py . "prod" ccs-cr start stopTime 

if len(sys.argv) < 4:
    print "Too few parameters"
    exit()

initDir = sys.argv[1] + "/"
database = sys.argv[2]
subsys = sys.argv[3]
start = int(sys.argv[4])
stop = int(sys.argv[5])
initFiles = [initDir + "refrigPlot.ini"] + [initDir + subsys + ".ini"]
# if len(sys.argv) > 4:
#     initFiles += [initDir + sys.argv[4] + ".ini"]


#****************************************************************************
#
#  Get database parameters from initialization file
#
#****************************************************************************

cfg = ConfigParser.ConfigParser()
cfg.read(initFiles)

server = cfg.get(database, "server")
port = cfg.get(database, "port")
dbname = cfg.get(database, "dbname")
user = cfg.get(database, "user")
password = cfg.get(database, "password")

if cfg.has_option("filter", "omit"):
    omitList = cfg.get("filter", "omit").split()
else:
    omitList = []
if cfg.has_option("filter", "keep"):
    keepList = cfg.get("filter", "keep").split()
else:
    keepList = []
for item in keepList:
    if item in omitList:
        omitList.remove(item)


#****************************************************************************
#
#  Global variables initialization
#
#****************************************************************************

gPoints = False
gGrid = False
gDbNames = []
gDbIds = []
gPlotNames = []
gPlotIds = []
gOverPlots = []
gFirstTimes = []
gLastTimes = []
gStartTime = None
gEndTime = None

dataFile = "/tmp/refrig_plot_" + str(os.getpid()) + ".dat"
cursor = None

ACTN_NONE = 0
ACTN_PLOT = 1
ACTN_SAVE = 2
ACTN_TEXT = 3
ACTN_STAT = 4


#****************************************************************************
#
#  Get console input
#
#  @param  prompt  The prompt to display
#
#  @return  The typed input, or None if EOF occurred (ctrl-D typed)
#
#****************************************************************************

def getInput(prompt):
    try:
        return raw_input(prompt)
    except:
        print
        return None


#****************************************************************************
#
#  Get the list of potential items to plot
#
#****************************************************************************

def getItems():
    global gDbNames, gDbIds
    count = cursor.execute("select srcName,id from datadesc where srcSubsystem = '"
                           + subsys + "' order by srcName")
    data = cursor.fetchall()
    for item in data:
        if item[0] not in omitList:
            gDbNames += [item[0]]
            gDbIds += [item[1]]
    return


#****************************************************************************
#
#  Display the list of potential items to plot
#
#****************************************************************************

def showItems():
    print "Available items:"
    n = 0
    posn = 0
    cWidth = 17
    lWidth = 4 * cWidth
    for name in gDbNames:
        item = "%3d: %s" % (n, name)
        size = cWidth * ((len(item) + cWidth) / cWidth)
        if posn + size > lWidth + 1:
            print
            posn = 0
        print "%-*s" % (size - 1, item),
        n += 1
        posn += size
    print


#****************************************************************************
#
#  Toggle the value of the points option
#
#****************************************************************************

def togglePoints():
    global gPoints
    gPoints =  not gPoints
    if gPoints:
        value = "enabled"
    else:
        value = "disabled"
    print "Points option", value


#****************************************************************************
#
#  Toggle the value of the grid option
#
#****************************************************************************

def toggleGrid():
    global gGrid
    gGrid = not gGrid
    if gGrid:
        value = "enabled"
    else:
        value = "disabled"
    print "Grid option", value


#****************************************************************************
#
#  Get a start or end time from the console
#
#  @param  prompt  The prompt to display
#
#  @param  start   The base time to use for time increments, or 0 if the
#                  current time is to be used.
#
#  @return  The entered time, as milliseconds since midnight January 1st,
#           1970 UT, or None if EOF occurred
#
#****************************************************************************

def getTime(prompt, start):
    while True:
        #
        #  Get typed input
        #
        tim = getInput(prompt)
        if tim == None: return None

        #
        #  Get +/- sign value and remove it along with leading/trailing blanks
        #
        tmo = re.match("^ *([-+]?) *([^ ]+) *([^ ]*) *(.*)$", tim)
        if tmo == None: continue
        tm = tmo.group(1, 2, 3, 4)
        if tm[3] != "":
            print "Invalid time"
            continue
        pfx = 0
        if tm[0] != "":
            if tm[0] == "-": pfx = -1
            else: pfx = 1
        tim = tm[1]
        if tm[2] != "": tim += " " + tm[2]

        #
        #  Process value with no sign ([YYYY-[MM-[DD ]]]HH:MM)
        #
        if pfx == 0:
            try:
                ts = time.strptime(tim, "%Y-%m-%d %H:%M")
            except:
                try:
                    ts = time.strptime(time.strftime("%Y-") + tim,
                                       "%Y-%m-%d %H:%M")
                except:
                    try:
                        ts = time.strptime(time.strftime("%Y-%m-") + tim,
                                           "%Y-%m-%d %H:%M")
                    except:
                        try:
                            ts = time.strptime(time.strftime("%Y-%m-%d ") + tim,
                                               "%Y-%m-%d %H:%M")
                        except:
                            print "Invalid time"
                            continue
            return 1000L * int(time.mktime(ts))

        #
        #  Process signed value
        #
        okay = (start != 0 or pfx == -1)
        tmo = re.match("^(\d+) (\d+):(\d+)$", tim)
        if tmo != None:
            td = tmo.group(1, 2, 3)
            tm = 60 * (int(td[2]) + 60 * (int(td[1]) + 24 * int(td[0])))
        else:
            tmo = re.match("^(\d+):(\d+)$", tim)
            if tmo != None:
                td = tmo.group(1, 2)
                tm = 60 * (int(td[1]) + 60 * (int(td[0])))
            else:
                tmo = re.match("^(\d+)$", tim)
                if tmo != None:
                    tm = 60 * int(tmo.group(1))
                else:
                    okay = False
        if okay:
            if pfx == -1: return 1000L * (int(time.time()) - tm)
            return start + 1000L * tm
        print "Invalid time"


#****************************************************************************
#
#  Get the names of the items to plot from the console, along with the
#  start and end times of the interval of interest
#
#  @return  0: if information obtained
#          -1: if EOF occurred
#
#****************************************************************************

def getPlots(reply, start = None, stop = None):
    global gPlotNames, gPlotIds, gOverPlots, gStartTime, gEndTime
    gStartTime = None
    gEndTime = None
    while gStartTime == None:
        if reply == None or re.match("^ *q *$", reply) != None:
            return -1
        if re.match("^ *\? *$", reply) != None:
            showItems()
            continue
        if re.match("^ *p *$", reply) != None:
            togglePoints()
            continue
        if re.match("^ *g *$", reply) != None:
            toggleGrid()
            continue
        pls = reply.split()
        if len(pls) == 0: continue
        gPlotNames = []
        gPlotIds = []
        gOverPlots = []
        icount = 0
        ocount = 0
        for pl in pls:
            op = None
            while pl != "":
                mo = re.match("^([+-]?)([^+-]*)(.*$)", pl)
#                if mo == None: break
                sign = mo.group(1)
                if op == None:
                    op = 0
                else:
                    if sign == "+": op = 1
                    if sign == "-": op = -1
                pi = mo.group(2)
                icount = icount + 1
                try:
                    index = int(pi)
                except:
                    print "Invalid integer"
                    break
                if index < 0 or index >= len(gDbNames):
                    print "Item number out of range"
                    break
                gPlotNames += [gDbNames[index]]
                gPlotIds += [gDbIds[index]]
                gOverPlots += [op]
                ocount += 1
                pl = mo.group(3)
            if ocount != icount: break
        if ocount != icount: continue
        while gEndTime == None:
            if start is None:
                gStartTime = getTime("Start time ([YYYY-[MM-]DD ]]]HH:MM "
                                + "| -[DD [HH:]]MM): ", 0)
            else:
                gStartTime = start
            if gStartTime == None: break
            if stop is None:
                gEndTime = getTime("End time ([YYYY-[MM-[DD ]]]HH:MM "
                              + "| {+|-}[DD [HH:]]MM): ", gStartTime)
            else: 
                gEndTime = stop
            #print gStartTime, gEndTime
    return 0


#****************************************************************************
#
#  Get the action to perform after a plot
#
#  @return  ACTN_NONE: no action
#           ACTN_PLOT: redraw the plot
#           ACTN_SAVE: save the plot in a file
#           ACTN_TEXT: save the data in a file for Excel
#           ACTN_STAT: produce statistics
#
#****************************************************************************

def getAction():
    reply = getInput("Action (s = save, a = average, p = ~points, g = ~grid, b = ~both): ")
    if reply == None:
        return ACTN_NONE
    if re.match("^ *s *$", reply) != None:
        return ACTN_SAVE
#    if re.match("^ *t *$", reply) != None:
#        return ACTN_TEXT
    if re.match("^ *a *$", reply) != None:
        return ACTN_STAT
    if re.match("^ *p *$", reply) != None:
        togglePoints()
        return ACTN_PLOT
    if re.match("^ *g *$", reply) != None:
        toggleGrid()
        return ACTN_PLOT
    if re.match("^ *b *$", reply) != None:
        togglePoints()
        toggleGrid()
        return ACTN_PLOT
    return ACTN_NONE


#****************************************************************************
#
#  Get the specified data
#
#  @param  id     The id of the data item to get
#
#  @param  start  The start time for the interval
#
#  @param  end    The end time for the interval
#
#  @return  The list of data items, which is empty if the name doesn't
#           exist, or there is no data in the specified time interval.
#
#****************************************************************************

def getData(id, start, end):
    count = cursor.execute("select tstampmills,doubleData from rawdata where "
                           + "descr_id = " + str(id) + " and tstampmills >= "
                           + str(start) + " and tstampmills <= " + str(end))
#                           + " order by tstampmills")
    return cursor.fetchall()


#****************************************************************************
#
#  Generate the Gnuplot input data file for a plot
#
#  @param  ix  The index of the item to plot
#
#  @return  True: if file generated successfully
#           False: if no data found or data file couldn't be opened
#
#****************************************************************************

def genData(ix):
    global gFirstTimes, gLastTimes
    data = getData(gPlotIds[ix], gStartTime, gEndTime)
    print len(data), "values found for", gPlotNames[ix]
    if len(data) == 0:
        return False
    try:
        out = open(dataFile + str(ix), "w")
    except:
        print "Cannot open output data file"
        return False
    to = -1
    ct = 0
    for item in data:
        ct = item[0] / 1000.0
        if to == -1:
            gFirstTimes += [ct]
            if time.localtime(ct)[8] == 0:
                to = time.timezone
            else:
                to = time.altzone
        out.write(str(ct - to) + " " + str(item[1]) + "\n")
    out.close()
    if ct != 0:
        gLastTimes += [ct]
    return True


#****************************************************************************
#
#  Display a plot of one or more (overlaid) items
#
#  @param  ixl  The list of the item indices to plot
#
#  @return  The plotter used to display the plot.  This is to be closed when
#           the plot is no longer needed.
#
#****************************************************************************

def showPlot(ixl):
    gp = os.popen("gnuplot -geometry 1200x900 -bg white", "w")
    sep = 'set title "' + subsys + ': '
    for ix in ixl:
        gp.write(sep + gPlotNames[abs(ix) - 1])
        sep = ' + '
    gp.write('" font "helvetica,25"\n')
    gp.write('set term x11 font "helvetica,20,,medium"\n')
    gp.write('set xdata time\n')
    gp.write('set timefmt "%s"\n')
    lft = time.localtime(gFirstTimes[ixl[0] - 1])
    llt = time.localtime(gLastTimes[ixl[0] - 1])
    if lft[0] != llt[0]:
        fmt = '%H:%M\\n%b %d\\n%Y'
    elif lft[2] != llt[2]:
        fmt = '%H:%M\\n%b %d'
    else:
        fmt = '%H:%M'
    gp.write('set xtics format "' + fmt + '"\n')
    if lft[0] == llt[0]:
        if lft[2] == llt[2]:
            fmt = '%b %d, %Y'
        else:
            fmt = '%Y'
        gp.write('set xlabel "' + time.strftime(fmt, lft) + '"\n')
    if gPoints:
        gp.write('set style data points\n')
    else:
        gp.write('set style data lines\n')
    if gGrid:
        gp.write('set grid xtics ytics\n')
#    gp.write('set ytics format "%.2f"\n')
    y2 = False
    for ix in ixl:
        if ix < 0: y2 = True
    if y2:
        gp.write('set ytics nomirror\n')
#        gp.write('set y2tics nomirror format "%.2f"\n')
        gp.write('set y2tics nomirror\n')
    gp.write('unset mouse\n')
    if len(ixl) == 1:
        gp.write('set key off\n')
    else:
        gp.write('set key on\n')
    sep = 'plot'
    for ix in ixl:
        rix = abs(ix) - 1
        gp.write(sep + ' "' + dataFile + str(rix) + '" using 1:2 title "'
                 + gPlotNames[rix] + '"')
        if ix < 0:
            gp.write(' axes x1y2')
        sep = ','
    gp.write('\n')
    gp.flush()
    return gp


#****************************************************************************
#
#  Save, to a file, a plot of one or more (overlaid) items
#
#  @param  ixl  The list of the item indices to plot
#
#****************************************************************************

def savePlot(ixl):
    y2 = False
    for ix in ixl:
        if ix < 0: y2 = True
    gp = os.popen("GDFONTPATH=/usr/share/fonts/default/Type1/ "
                    + "gnuplot -bg white", "w")
    sep = 'set title "' + subsys + ': '
    for ix in ixl:
        gp.write(sep + gPlotNames[abs(ix) - 1])
        sep = ' + '
    gp.write('" font "b018012l,18"\n')  ## Bookman
    gp.write('set terminal jpeg size 1200,900 font "b018012l" 12\n')
    sep = 'set output "./'
    for ix in ixl:
        gp.write(sep + gPlotNames[abs(ix) - 1])
        sep = '_'
    gp.write('_' + time.strftime("%Y%m%d_%H%M%S") + '.jpg"\n')
    gp.write('set lmargin 10\n')
    if y2:
        gp.write('set rmargin 10\n')
    else:
        gp.write('set rmargin 4\n')
    gp.write('set tmargin 4\n')
    gp.write('set bmargin 4\n')
    gp.write('set xdata time\n')
    gp.write('set timefmt "%s"\n')
    lft = time.localtime(gFirstTimes[ixl[0] - 1])
    llt = time.localtime(gLastTimes[ixl[0] - 1])
    if lft[0] != llt[0]:
        fmt = '%H:%M\\n%b %d\\n%Y'
    elif lft[2] != llt[2]:
        fmt = '%H:%M\\n%b %d'
    else:
        fmt = '%H:%M'
    gp.write('set xtics format "' + fmt + '"\n')
    if lft[0] == llt[0]:
        if lft[2] == llt[2]:
            fmt = '%b %d, %Y'
        else:
            fmt = '%Y'
        gp.write('set xlabel "' + time.strftime(fmt, lft) + '"\n')
    if gPoints:
        gp.write('set style data points\n')
    else:
        gp.write('set style data lines\n')
    if gGrid:
        gp.write('set grid xtics ytics\n')
#    gp.write('set ytics format "%.2f"\n')
    if y2:
        gp.write('set ytics nomirror\n')
#        gp.write('set y2tics nomirror format "%.2f"\n')
        gp.write('set y2tics nomirror\n')
    if len(ixl) == 1:
        gp.write('set key off\n')
    else:
        gp.write('set key on\n')
    sep = 'plot'
    for ix in ixl:
        rix = abs(ix) - 1
        gp.write(sep + ' "' + dataFile + str(rix) + '" using 1:2 title "'
                 + gPlotNames[rix] + '"')
        if ix < 0:
            gp.write(' axes x1y2')
        sep = ','
    gp.write('\n')
    gp.close()


#****************************************************************************
#
#  Save, to a text file, the data for one or more (overlaid) items
#
#  @param  ixl  The list of the item indices to save
#
#****************************************************************************

def saveText(ixl):
    ifl = []
    lnl = []
    tol = []
    spl = []
    ip = 0

    try:
        out = open("Output file", "w")
    except:
        print "Cannot open output text file"
        return

    for ix in ixl:
        ixa = abs(ix) - 1
        name = dataFile + str(ixa)
        try:
            inf = open(name, "r")
        except:
            print "Cannot open input data file (" + name + ")"
            continue
        ifl += [inf]
        lnl += inf.readline().split()
        tol.insert(findNearest(inl[ip], tol), ip)
        spl += [(ip + 1) * ","]
        ip += 1

    while len(tol) > 0:
        ip = tol.pop(0)
        data = inl[ip]
        time = getTime(data[0])
        out.write(time + spl[ip] + data[1])
        inl[ip] = ifl[ip].readline().split()
        if inl[ip] != None:
            tol.insert(findNearest(inl[ip], tol), ip)
        else:
            ifl[ip].close()

    out.close()
    return


#****************************************************************************
#
#  Display statistical data for one or more (overlaid) items
#
#  @param  ixl  The list of the item indices to show
#
#****************************************************************************

def showStats(ixl):
    for ix in ixl:
        ixa = abs(ix) - 1
        name = dataFile + str(ixa)
        try:
            inf = open(name, "r")
        except:
            print "Cannot open input data file (" + name + ")"
            continue
        minm = 1.0e30
        maxm = -1.0e30
        deltaTime = 1.0
        total = 0.0
        totalTime = 0.0
        time = 0.0
        while True:
            flds = inf.readline().split()
            if len(flds) != 0:
                nextTime = float(flds[0])
                nextValue = float(flds[1])
                minm = min(nextValue, minm)
                maxm = max(nextValue, maxm)
                if time != 0.0:
                    deltaTime = nextTime - time
                    total += deltaTime * value
                    totalTime += deltaTime
                time = nextTime
                value = nextValue
            else:
                if time != 0.0:
                    total += deltaTime * value
                    totalTime += deltaTime
                break
        inf.close()
        print "%s: Avg. = %.2f, Min. = %.2f, Max. = %.2f" \
               % (gPlotNames[ixa], total / totalTime, minm, maxm)


#****************************************************************************
#
#  Perform an action
#
#****************************************************************************

def takeAction(actn, gil):
    ixl = []
    gpl = []
    for ix in range(len(gPlotNames)):
        if gOverPlots[ix] == 0: ixl = []
        if gil[ix]:
            if gOverPlots[ix] >= 0:
                ixl += [ix + 1]
            else:
                ixl += [-(ix + 1)]
        if (ix + 1 >= len(gPlotNames) or gOverPlots[ix + 1] == 0) and len(ixl) != 0:
            if actn == ACTN_PLOT:
                gpl += [showPlot(ixl)]
            if actn == ACTN_SAVE:
                savePlot(ixl)
            if actn == ACTN_TEXT:
                saveText(ixl)
            if actn == ACTN_STAT:
                showStats(ixl)
    return gpl


#****************************************************************************
#
#  Main code
#
#****************************************************************************

# first = True

# while True:
#     db = MySQLdb.connect(server, user, password, dbname, port=int(port))
#     cursor = db.cursor()

#     if first:
#         getItems()
#         showItems()
#         first = False

#     if getPlots() != 0: break

#     gFirstTimes = []
#     gLastTimes = []
#     gil = []
#     for ix in range(len(gPlotNames)):
#         gil.append(genData(ix))

#     gpl = []
#     action = ACTN_PLOT

#     while action != ACTN_NONE:

#         if action == ACTN_PLOT:
#             gpl = takeAction(action, gil)

#         action = getAction()
#         gpl = []    # Closes plot windows

#         if action != ACTN_NONE and action != ACTN_PLOT:
#             takeAction(action, gil)
            
#     db.close()



if __name__ == '__main__':
    #start = int((time.time()-600)*1000)
    #stop = int(time.time()*1000)
    #print start, stop

    db = MySQLdb.connect(server, user, password, dbname, port=int(port))
    cursor = db.cursor()

    #reply = getInput("Item numbers (or ?, q, p, g): ")
    getItems()

    reply = "57 58 59 60 61 62" # Selects WREB.Temp1 - Temp6
    getPlots(reply, start, stop)

    gFirstTimes = []
    gLastTimes = []
    gil = []
    for ix in range(len(gPlotNames)):
        gil.append(genData(ix))

    gpl = []
    action = ACTN_SAVE
    takeAction(action, gil)

    # while action != ACTN_NONE:

    #     if action == ACTN_PLOT:
    #         gpl = takeAction(action, gil)

    #     action = getAction()
    #     gpl = []    # Closes plot windows

    #     if action != ACTN_NONE and action != ACTN_PLOT:
    #         takeAction(action, gil)
            
    db.close()