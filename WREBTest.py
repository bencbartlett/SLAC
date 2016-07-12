# WREB Testing Script
# Originally written by Sven Herrmann
# Restructured/augmented by Ben Bartlett (bcb@slac.stanford.edu)

# To run:
# Ensure Jython console is running (./JythonConsole or the bootstrapper program)
# Ensure crRun.sh is running
# Ensure DACs are loaded in the CCS console
# "python WREBTest.py [options]"


from __future__ import print_function

import glob
import os
import shutil
import signal
import textwrap
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from astropy.io import fits
from WREBTestPDFGen import *

from Libraries.FastProgressBar import progressbar
from Libraries.PythonBinding import *

start = int(1000*time.time())

# Catch abort so previous settings can be restored
def exitScript():
    # Bring back the saved temp config
    print ("\nTests concluded or ^C raised. Restoring saved temp config and exiting...")
    jy.do('raftsub.synchCommandLine(1000,"loadCategories Rafts:WREB_temp_cfg")')
    jy.do('wreb.synchCommandLine(1000,"loadDacs true")')    
    jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')    
    jy.do('wreb.synchCommandLine(1000,"loadAspics true")')   
signal.signal(signal.SIGINT, exitScript)

# ---------- Helper functions ----------
def stepRange(start, end, step):
    while start <= end:
        yield start
        start += step
def voltsToSHDAC(volt, Rfb, Rin):
    dac=(volt*4095/5/(-Rfb/Rin))
    if dac > 4095 : dac=4095
    if dac < 0    : dac =0
    return dac
def voltsToDAC(volt, shvolt, Rfb, Rin):
    dac = ((volt - shvolt) * 4095/5/(1+Rfb/Rin) )
    if dac > 4095 : dac=4095
    if dac < 0    : dac =0
    return dac

def convert(value, type_):
    '''Converts a value to the specified type'''
    import importlib
    try:
        # Check if it's a builtin type
        module = importlib.import_module('__builtin__')
        cls = getattr(module, type_)
    except AttributeError:
        # if not, separate module and class
        module, type_ = type_.rsplit(".", 1)
        module        = importlib.import_module(module)
        cls           = getattr(module, type_)
    return cls(value)

def printv(string):
    if verbose:
        print (string)

class JythonInterface(CcsJythonInterpreter):
    '''Some hacky workarounds to communicate both ways with Jython.'''
    def do(self, code):
        '''Execute a command on the CCS Jython interpreter.'''
        return self.syncExecution(code)

    def get(self, code, dtype = "float"):
        '''Executes a piece of code and returns the value through getOutput().
           getOutput() normally only returns the results of cout, so the result
           is automatically typecasted to type dtype.
           This should be used only with a single command at a time. Like I said,
           hacky work around, this should be fixed in the future.'''
        result = self.syncExecution("print ("+code+")").getOutput()
        return convert(result, dtype)


# ------------ Tests ------------

class IdleCurrentConsumption(object):
    def __init__(self):
        self.title = "Idle Current"
        self.passed = "N/A"
        self.stats = "N/A"
        # Idle Current Consumption
        print ("Running idle current test...")
        DigPS_V  = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DigPS_V").getResult()')
        DigPS_I  = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DigPS_I").getResult()')
        AnaPS_V  = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.AnaPS_V").getResult()')
        AnaPS_I  = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.AnaPS_I").getResult()')
        ODPS_V   = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_V").getResult()')
        ODPS_I   = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_I").getResult()')
        ClkHPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_V").getResult()')
        ClkHPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_I").getResult()')
        DphiPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_V").getResult()')
        DphiPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_I").getResult()')
        HtrPS_V  = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.HtrPS_V").getResult()')
        HtrPS_I  = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.HtrPS_I").getResult()')

        printv("Idle  current consumption test:")
        printv("DigPS_V[V]:   %5.2f   DigPS_I[mA]:  %7.2f" % (DigPS_V, DigPS_I))
        printv("AnaPS_V[V]:   %5.2f   AnaPS_I[mA]:  %7.2f" % (AnaPS_V, AnaPS_I))
        printv("ODPS_V[V]:    %5.2f   ODPS_I[mA]:   %7.2f" % (ODPS_V, ODPS_I))
        printv("ClkHPS_V[V]:  %5.2f   ClkHPS_I[mA]: %7.2f" % (ClkHPS_V, ClkHPS_I))
        printv("DphiPS_V[V]v: %5.2f   DphiPS_I[mA]: %7.2f" % (DphiPS_V, DphiPS_I) )
        printv("HtrPS_V[V]:   %5.2f   HtrPS_I[mA]:  %7.2f" % (HtrPS_V, HtrPS_I) )

        self.voltages = [("DigPS_V", DigPS_V), ("AnaPS_V", AnaPS_V), ("ODPS_V", ODPS_V),
                    ("ClkHPS_V", ClkHPS_V), ("DphiPS_V", DphiPS_V), ("HtrPS_V", HtrPS_V)]
        self.currents = [("DigPS_I", DigPS_I), ("AnaPS_I", AnaPS_I), ("ODPS_I", ODPS_I),
                    ("ClkHPS_I", ClkHPS_I), ("DphiPS_I", DphiPS_I), ("HtrPS_I", HtrPS_I)]

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.idleCurrent("Idle Current Test", self.voltages, self.currents)

class ChannelTest(object):
    def __init__(self):
        # Full list of channels
        self.title = "Channel Comms"
        # TODO: Fix list of channels, add better pass metric
        fullChannels = ['WREB.Temp1', 'WREB.Temp2', 'WREB.Temp3', 'WREB.Temp4', 'WREB.Temp5', 'WREB.Temp6', 'WREB.CCDtemp',
                        'WREB.DigPS_V', 'WREB.DigPS_I', 'WREB.AnaPS_V', 'WREB.AnaPS_I', 'WREB.ODPS_V', 'WREB.ODPS_I',
                        'WREB.ClkHPS_V', 'WREB.ClkHPS_I', 'WREB.DphiPS_V', 'WREB.DphiPS_I', 'WREB.HtrPS_V', 'WREB.HtrPS_I',
                        'WREB.VREF25', 'WREB.OD_V', 'WREB.OD_I', 'WREB.OG_V', 'WREB.RD_V', 'WREB.GD_V', 'WREB.CKP_V',
                        'WREB.CKPSH_V', 'WREB.CKS_V', 'WREB.SCKU_V', 'WREB.SCKL_V', 'WREB.RG_V', 'WREB.RGU_V', 'WREB.RGL_V']

        self.channels = jy.get('raftsub.synchCommandLine(1000,"getChannelNames").getResult()', dtype = 'str')
        self.channels = self.channels.replace("[","").replace("]","").replace("\n","")
        self.channels = self.channels.split(", ") # Channels is now a list of strings representing channel names
        pbar = progressbar("Channel Comms Test, &count&: ", len(self.channels))
        if not verbose: pbar.start()

        # Primitive pass metric: test if channel list has all channels in it
        self.passed = "PASS"
        if set(self.channels) != set(fullChannels):
            self.passed = "FAIL"

        # Attempt to get value from everything in channels
        self.vals = []
        for channel in self.channels:
            val = jy.get('raftsub.synchCommandLine(1000,"getChannelValue '+channel+'").getResult()')
            printv("Channel: {0:>10}  Value: {1:6.3f}".format(channel, val))
            self.vals.append(val)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.stats = "%i/%i channels missing." % (len(fullChannels)-len(self.channels), len(fullChannels))

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.add_page()
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 6, "Channel Communications Test", 0, 1, 'L', 1)
        pdf.columnTable([self.channels, self.vals], colHeaders = ["Channel", "Value"], fontSize = 12)


class ASPICcommsTest(object):
    def __init__(self):
        self.title = "ASPIC Comms"
        self.aspicstr = jy.get('raftsub.synchCommandLine(1000,"checkAspics").getResult()', dtype = 'str')
        aspics = self.aspicstr.replace("[", "").replace("]", "").replace("\n", "")
        aspics = aspics.split(", ")  # Channels is now a list of strings representing channel names

        # Primitive pass metric: test if channel list has all channels in it
        numAspics = 0
        self.passed = "PASS"
        for aspic in aspics:
            if aspic != "0":
                self.passed = "FAIL"
            else:
                numAspics += 1

        self.stats = "%i/%i ASPICS communicating." % (numAspics, len(aspics))

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.add_page()
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 6, "ASPIC Communications Test", 0, 1, 'L', 1)
        pdf.cell(0, 6, "Test " + self.passed + ". " + self.stats, 0, 1, 'L')
        pdf.cell(0, 6, "ccs-cr.checkAsics result: " + self.aspicstr, 0, 1, 'L')

class CSGate(object):
    def __init__(self):
        self.title = "CS Gate Test"
        # CSGate
        pbar = progressbar("CS Gate Test, &count&: ", 21)
        if not verbose: pbar.start()
        # Arrays for report
        CSGV_arr        = []
        WREB_OD_I_arr   = []
        WREB_ODPS_I_arr = []
        for CSGV in stepRange(0, 5, 0.25):
            CSGdac = voltsToDAC(CSGV, 0, 1, 1e6)
            printv("%5.2f\t%4i" % (CSGV, CSGdac)),
            jy.do('wrebBias.synchCommandLine(1000,"change csGate %d")' % CSGdac)
            jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            WREB_OD_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_I").getResult()')
            WREB_ODPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ODPS_I").getResult()')
            printv("\t%5.2f\t%5.2f" % (WREB_OD_I, WREB_ODPS_I))
            # Add to arrays to make plots for report
            CSGV_arr.append(CSGV)
            WREB_OD_I_arr.append(WREB_OD_I)
            WREB_ODPS_I_arr.append(WREB_ODPS_I)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        # Return to report generator
        self.data = ((CSGV_arr, "CSGV (V)"), (WREB_OD_I_arr, "WREB.OD_I (mA)"), (WREB_ODPS_I_arr, "WREB.ODPS_I (mA)"))
        # TODO: Implement pass/stats metrics
        self.passed = "N/A"
        self.stats = "N/A"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.makePlotPage("CSGate Test", "CSGate.jpg", self.data)
        pdf.columnTable(self.data)

class PCKRails(object):
    def __init__(self):
        self.title = "PCK Rails"
        # PCK rails
        pbar = progressbar("PCK Rails Test, &count&: ", 25)
        if not verbose: pbar.start()
        printv("\nrail voltage generation for PCLK test ")
        PCLKDV     = 5 #delta voltage between lower and upper
        PCLKLshV   = -8.0 #sets the offset shift to -8V on the lower
        PCLKUshV   = -2 #PCLKLshV+PCLKDV    #sets the offset shift on the upper
        PCLKLshDAC = voltsToSHDAC(PCLKLshV, 49.9, 20)
        PCLKUshDAC = voltsToSHDAC(PCLKUshV, 49.9, 20)
        printv("-8V and 5V amplitude set  ")
        time.sleep(tsoak)
        printv("PCLKLsh[V]: %5.2f   PCLKUsh[V]: %5.2f   PCLKLsh_DACval[ADU]: %4i   PCLKUsh_DACval[ADU]: %4i " %
               (PCLKLshV, PCLKUshV, PCLKLshDAC, PCLKUshDAC) )
        printv("PCLKLV[V]\tPCLKLV_DAC[ADU]\tPCLKUV[V]\tPCLKUV_DAC[ADU]\tWREB.PCLKL_V[V]\tWREB.PCLKU_V[V]")
        # Report arrays
        PCLKLV_arr        = []
        PCLKLdac_arr      = []
        PCLKUV_arr        = []
        PCLKUdac_arr      = []
        WREB_CKPSH_V_arr  = []
        WREB_DphiPS_V_arr = []
        deltaPCLKLV_arr   = []
        deltaPCLKUV_arr   = []
        for PCLKLV in stepRange(PCLKLshV, PCLKLshV+12, 0.5):
            PCLKLdac = voltsToDAC(PCLKLV, PCLKLshV, 49.9, 20)
            PCLKUV   = PCLKLV+PCLKDV
            PCLKUdac = voltsToDAC(PCLKUV, PCLKUshV, 49.9, 20)
            printv("%5.2f\t%4i\t%5.2f\t%4i" % (PCLKLV, PCLKLdac, PCLKUV, PCLKUdac) ),
            jy.do('wrebDAC.synchCommandLine(1000,"change pclkLowSh %d")' % PCLKLshDAC)
            jy.do('wrebDAC.synchCommandLine(1000,"change pclkLow %d")' % PCLKLdac)
            jy.do('wrebDAC.synchCommandLine(1000,"change pclkHighSh %d")' % PCLKUshDAC)
            jy.do('wrebDAC.synchCommandLine(1000,"change pclkHigh %d")' % PCLKUdac)
            jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
            time.sleep(tsoak)
            WREB_CKPSH_V  = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.CKPSH_V").getResult()')
            WREB_DphiPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_V").getResult()')
            printv("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
                   (WREB_CKPSH_V, WREB_DphiPS_V, (PCLKLV - WREB_CKPSH_V), (PCLKUV - WREB_DphiPS_V)) )
            # Append to arrays
            PCLKLV_arr        .append(PCLKLV)
            PCLKLdac_arr      .append(PCLKLdac)
            PCLKUV_arr        .append(PCLKUV)
            PCLKUdac_arr      .append(PCLKUdac)
            WREB_CKPSH_V_arr  .append(WREB_CKPSH_V)
            WREB_DphiPS_V_arr .append(WREB_DphiPS_V)
            deltaPCLKLV_arr   .append(PCLKLV - WREB_CKPSH_V)
            deltaPCLKUV_arr   .append(PCLKUV - WREB_DphiPS_V)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((PCLKLV_arr, "PCLKLV (V)"),
                (PCLKUV_arr, "PCLKUV (V)"),
                (WREB_CKPSH_V_arr, "WREB.CKPSH_V (V)"),
                (WREB_DphiPS_V_arr, "WREB.DphiPS_V (V)"))
        self.residuals = ((deltaPCLKLV_arr, "deltaPCLKLV_arr (V)"),
                     (deltaPCLKUV_arr, "deltaPCLKUV_arr (V)"))
        # TODO: Pass metric
        self.passed = "N/A"
        self.stats = "N/A"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.makeResidualPlotPage("PCKRails Test", "tempFigures/PCKRails.jpg", self.data, self.residuals)


class SCKRails(object):
    def __init__(self):
        self.title = "SCK Rails"
        # SCK rails
        pbar = progressbar("SCK Rails Test, &count&: ", 25)
        if not verbose: pbar.start()
        printv("\nrail voltage generation for SCLK test ")
        SCLKDV     = 5 #delta voltage between lower and upper
        SCLKLshV   = -8.5 #sets the offset shift to -8V on the lower
        SCLKUshV   = -2 # SCLKLshV+SCLKDV    #sets the offset shift on the upper
        SCLKLshDAC = voltsToSHDAC(SCLKLshV, 49.9, 20)
        SCLKUshDAC = voltsToSHDAC(SCLKUshV, 49.9, 20)
        printv("-8V and 5V amplitude set  ")
        time.sleep(tsoak)
        printv("SCLKLsh[V]: %5.2f   SCLKUsh[V]: %5.2f   SCLKLsh_DACval[ADU]: %4i   SCLKUsh_DACval[ADU]: %4i " %
               (SCLKLshV, SCLKUshV, SCLKLshDAC, SCLKUshDAC) )
        printv("SCLKLV[V]\tSCLKLV_DAC[ADU]\tSCLKUV[V]\tSCLKUV_DAC[ADU]\tWREB.SCLKL_V[V]\tWREB.SCLKU_V[V]")
        # Report arrays
        SCLKLV_arr      = []
        SCLKLdac_arr    = []
        SCLKUV_arr      = []
        SCLKUdac_arr    = []
        WREB_SCKL_V_arr = []
        WREB_SCKU_V_arr = []
        deltaSCLKLV_arr = []
        deltaSCLKUV_arr = []
        for SCLKLV in stepRange(SCLKLshV, SCLKLshV+12, 0.5):
            SCLKLdac = voltsToDAC(SCLKLV, SCLKLshV, 49.9, 20)
            SCLKUV   = SCLKLV+SCLKDV
            SCLKUdac = voltsToDAC(SCLKUV, SCLKUshV, 49.9, 20)
            printv("%5.2f\t%4i\t%5.2f\t%4i" % (SCLKLV, SCLKLdac, SCLKUV, SCLKUdac) ),
            jy.do('wrebDAC.synchCommandLine(1000,"change sclkLowSh %d")' % SCLKLshDAC)
            jy.do('wrebDAC.synchCommandLine(1000,"change sclkLow %d")' % SCLKLdac)
            jy.do('wrebDAC.synchCommandLine(1000,"change sclkHighSh %d")' % SCLKUshDAC)
            jy.do('wrebDAC.synchCommandLine(1000,"change sclkHigh %d")' % SCLKUdac)
            jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
            time.sleep(tsoak)
            WREB_SCKL_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKL_V").getResult()')
            WREB_SCKU_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKU_V").getResult()')
            printv("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
                   (WREB_SCKL_V, WREB_SCKU_V, (SCLKLV - WREB_SCKL_V), (SCLKUV - WREB_SCKU_V)) )
            # Append to arrays
            SCLKLV_arr        .append(SCLKLV)
            SCLKLdac_arr      .append(SCLKLdac)
            SCLKUV_arr        .append(SCLKUV)
            SCLKUdac_arr      .append(SCLKUdac)
            WREB_SCKL_V_arr   .append(WREB_SCKL_V)
            WREB_SCKU_V_arr   .append(WREB_SCKU_V)
            deltaSCLKLV_arr   .append(SCLKLV - WREB_SCKL_V)
            deltaSCLKUV_arr   .append(SCLKUV - WREB_SCKU_V)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((SCLKLV_arr, "SCLKLV (V)"),
                (SCLKUV_arr, "SCLKUV (V)"),
                (WREB_SCKL_V_arr, "WREB.SCKL_V (V)"),
                (WREB_SCKU_V_arr, "WREB.SCKU_V (V)"))
        self.residuals = ((deltaSCLKLV_arr, "deltaSCLKLV (V)"),
                     (deltaSCLKUV_arr, "deltaSCLKUV (V)"))

        # Give pass/fail result
        self.passed       = "PASS"
        allowedError = 0.25 # Some arbitrary value giving the allowable residual error
        maxFails     = 4 # Some value giving the maximum number of allowed failures
        numErrors    = 0
        totalPoints  = 0
        for residual in deltaSCLKLV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1
        for residual in deltaSCLKUV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        ml, bl = np.polyfit(SCLKLV_arr, WREB_SCKL_V_arr, 1)
        mu, bu = np.polyfit(SCLKUV_arr, WREB_SCKU_V_arr, 1)
        self.stats  = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % \
            (ml, mu, totalPoints-numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(ml - 1.0) > 0.05 or abs(mu - 1.0) > 0.05:
            self.passed = "FAIL"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.residualTest("SCK Rails Test", self.data, self.residuals, self.passed, self.stats)

class SCKRailsDiverging(object):
    def __init__(self, amplitude, startV):
        self.title = "Diverging SCK Rails"
        self.amplitude = amplitude
        self.startV = startV
        '''Diverging SCK Rails test. Amplitude is half-wave maximum divergence,
        startV is initial voltage to start LV=UV diverging from.'''
        step = 0.5
        pbar = progressbar("Diverging SCK Rails Test, &count&: ", amplitude / step + 1)
        if not verbose: pbar.start()
        printv("\nDiverging rail voltage generation for SCLK test ")
        SCLKLshV   = startV - amplitude # Shift to minimum needed voltage, this is added back in later
        SCLKUshV   = startV
        SCLKLshDAC = voltsToSHDAC(SCLKLshV, 49.9, 20)
        SCLKUshDAC = voltsToSHDAC(SCLKUshV, 49.9, 20)
        jy.do('wrebDAC.synchCommandLine(1000,"change sclkLowSh %d")' % SCLKLshDAC)
        jy.do('wrebDAC.synchCommandLine(1000,"change sclkHighSh %d")' % SCLKUshDAC)
        printv("-8V and 5V amplitude set  ")
        time.sleep(tsoak)
        # printv("SCLKLsh[V]: %5.2f   SCLKUsh[V]: %5.2f   SCLKLsh_DACval[ADU]: %4i   SCLKUsh_DACval[ADU]: %4i " % (SCLKLshV, SCLKUshV, SCLKLshDAC, SCLKUshDAC) )
        printv("SCLKLV[V]\tSCLKLV_DAC[ADU]\tSCLKUV[V]\tSCLKUV_DAC[ADU]\tWREB.SCLKL_V[V]\tWREB.SCLKU_V[V]")
        # Report arrays
        SCLKLV_arr      = []
        SCLKLdac_arr    = []
        SCLKUV_arr      = []
        SCLKUdac_arr    = []
        WREB_SCKL_V_arr = []
        WREB_SCKU_V_arr = []
        deltaSCLKLV_arr = []
        deltaSCLKUV_arr = []
        ClkHPS_I_arr    = []
        for SCLKDV in stepRange(0, amplitude, step):
            SCLKLV = startV - SCLKDV
            SCLKUV = startV + SCLKDV
            SCLKLdac = voltsToDAC(SCLKLV + amplitude, startV, 49.9, 20) # Add the amplitude back in
            SCLKUdac = voltsToDAC(SCLKUV, startV, 49.9, 20)
            printv("%5.2f\t%4i\t%5.2f\t%4i" % (SCLKLV, SCLKLdac, SCLKUV, SCLKUdac) ),
            jy.do('wrebDAC.synchCommandLine(1000,"change sclkLow %d")' % SCLKLdac)
            jy.do('wrebDAC.synchCommandLine(1000,"change sclkHigh %d")' % SCLKUdac)
            jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
            time.sleep(tsoak)
            WREB_SCKL_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKL_V").getResult()')
            WREB_SCKU_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKU_V").getResult()')
            ClkHPS_I = 0.1*jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_I").getResult()')
            printv("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
                   (WREB_SCKL_V, WREB_SCKU_V, (SCLKLV - WREB_SCKL_V), (SCLKUV - WREB_SCKU_V)) )
            # Append to arrays
            SCLKLV_arr        .append(SCLKLV)
            SCLKLdac_arr      .append(SCLKLdac)
            SCLKUV_arr        .append(SCLKUV)
            SCLKUdac_arr      .append(SCLKUdac)
            WREB_SCKL_V_arr   .append(WREB_SCKL_V)
            WREB_SCKU_V_arr   .append(WREB_SCKU_V)
            deltaSCLKLV_arr   .append(SCLKLV - WREB_SCKL_V)
            deltaSCLKUV_arr   .append(SCLKUV - WREB_SCKU_V)
            ClkHPS_I_arr      .append(ClkHPS_I)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((SCLKLV_arr, "SCLKLV (V)"),
                (SCLKUV_arr, "SCLKUV (V)"),
                (WREB_SCKL_V_arr, "WREB.SCKL_V (V)"),
                (WREB_SCKU_V_arr, "WREB.SCKU_V (V)"),
                (ClkHPS_I_arr, "ClkHPS_I (10mA)"))
        self.residuals = ((deltaSCLKLV_arr, "deltaSCLKLV (V)"),
                     (deltaSCLKUV_arr, "deltaSCLKUV (V)"))

        # Give pass/fail result
        self.passed       = "PASS"
        allowedError = 0.25 # Some arbitrary value giving the allowable residual error
        maxFails     = 4 # Some value giving the maximum number of allowed failures
        numErrors    = 0
        totalPoints  = 0
        for residual in deltaSCLKLV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1
        for residual in deltaSCLKUV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        ml, bl = np.polyfit(SCLKLV_arr, WREB_SCKL_V_arr, 1)
        mu, bu = np.polyfit(SCLKUV_arr, WREB_SCKU_V_arr, 1)
        self.stats  = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % \
            (ml, mu, totalPoints-numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(ml - 1.0) > 0.05 or abs(mu - 1.0) > 0.05:
            self.passed = "FAIL"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.makeResidualPlotPage("Diverging SCKRails Test %i V" % int(self.startV),
                                 "tempFigures/divergingSCKRails %i.jpg" % int(self.startV),
                                 self.data,
                                 self.residuals,
                                 pltRange = [-12, 12])
        pdf.cell(epw, pdf.font_size, self.stats, align = 'C', ln = 1)
        pdf.passFail(self.passed)
        pdf.columnTable(self.data + self.residuals)


class RGRails(object):
    def __init__(self):
        self.title = "RG Rails"
        # RG rails
        pbar = progressbar("RG Rails Test, &count&: ", 25)
        if not verbose: pbar.start()
        printv("\nrail voltage generation for RG test ")
        RGDV     = 5 #delta voltage between lower and upper
        RGLshV   = -8.5 #sets the offset shift to -8.5V on the lower
        RGUshV   = -2.5 # RGLshV+RGDV    #sets the offset shift on the upper
        RGLshDAC = voltsToSHDAC(RGLshV, 49.9, 20)
        RGUshDAC = voltsToSHDAC(RGUshV, 49.9, 20)
        printv("-8V and 5V amplitude set  ")
        time.sleep(tsoak)
        printv("RGLsh[V]: %5.2f   RGUsh[V]: %5.2f   RGLsh_DACval[ADU]: %4i   RGUsh_DACval[ADU]: %4i " %
               (RGLshV, RGUshV, RGLshDAC, RGUshDAC) )
        printv("RGLV[V]\tRGLV_DAC[ADU]\tRGUV[V]\tRGUV_DAC[ADU]\tWREB.RGL_V[V]\tWREB.RGU_V[V]")
        # Report arrays
        RGLV_arr       = []
        RGLdac_arr     = []
        RGUV_arr       = []
        RGUdac_arr     = []
        WREB_RGL_V_arr = []
        WREB_RGU_V_arr = []
        deltaRGLV_arr  = []
        deltaRGUV_arr  = []
        for RGLV in stepRange(RGLshV, RGLshV+12, 0.5): #step trough the lower rail range
            RGLdac = voltsToDAC(RGLV, RGLshV, 49.9, 20)
            RGUV   = RGLV+RGDV #adds the delta voltage to the upper rail
            RGUdac = voltsToDAC(RGUV, RGUshV, 49.9, 20)
            printv("%5.2f\t%4i\t%5.2f\t%4i" % (RGLV, RGLdac, RGUV, RGUdac) ),
            jy.do('wrebDAC.synchCommandLine(1000,"change rgLowSh %d")' % RGLshDAC)
            jy.do('wrebDAC.synchCommandLine(1000,"change rgLow %d")' % RGLdac)
            jy.do('wrebDAC.synchCommandLine(1000,"change rgHighSh %d")' % RGUshDAC)
            jy.do('wrebDAC.synchCommandLine(1000,"change rgHigh %d")' % RGUdac)
            jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
            time.sleep(tsoak)
            WREB_RGL_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RGL_V").getResult()')
            WREB_RGU_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RGU_V").getResult()')
            printv("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" % (WREB_RGL_V, WREB_RGU_V, (RGLV - WREB_RGL_V), (RGUV - WREB_RGU_V)) )
            # Append to arrays
            RGLV_arr        .append(RGLV)
            RGLdac_arr      .append(RGLdac)
            RGUV_arr        .append(RGUV)
            RGUdac_arr      .append(RGUdac)
            WREB_RGL_V_arr  .append(WREB_RGL_V)
            WREB_RGU_V_arr  .append(WREB_RGU_V)
            deltaRGLV_arr   .append(RGLV - WREB_RGL_V)
            deltaRGUV_arr   .append(RGUV - WREB_RGU_V)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((RGLV_arr, "RGLV (V)"),
                (RGUV_arr, "RGUV (V)"),
                (WREB_RGL_V_arr, "WREB.RGL_V (V)"),
                (WREB_RGU_V_arr, "WREB.RGU_V (V)"))
        self.residuals = ((deltaRGLV_arr, "deltaRGLV (V)"),
                     (deltaRGUV_arr, "deltaRGUV (V)"))

        # Give pass/fail result
        self.passed  = "PASS"
        allowedError = 0.25 # Some arbitrary value giving the allowable residual error
        maxFails     = 4 # Some value giving the maximum number of allowed failures
        numErrors    = 0
        totalPoints  = 0
        for residual in deltaRGLV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1
        for residual in deltaRGUV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        ml, bl = np.polyfit(RGLV_arr, WREB_RGL_V_arr, 1)
        mu, bu = np.polyfit(RGUV_arr, WREB_RGU_V_arr, 1)
        self.stats  = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % \
            (ml, mu, totalPoints-numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(ml - 1.0) > 0.05 or abs(mu - 1.0) > 0.05:
            self.passed = "FAIL"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.residualTest("RG Rails Test", self.data, self.residuals, self.passed, self.stats)


class RGRailsDiverging(object):
    def __init__(self, amplitude, startV):
        self.title = "Diverging RG Rails"
        self.amplitude = amplitude
        self.startV = startV
        '''Diverging RG Rails test. Amplitude is half-wave maximum divergence,
        startV is initial voltage to start LV=UV diverging from.'''
        step = 0.5
        pbar = progressbar("Diverging RG Rails Test, &count&: ", amplitude / step + 1)
        if not verbose: pbar.start()
        printv("\nDiverging rail voltage generation for RG test ")
        RGLshV   = startV - amplitude # Shift to minimum needed voltage, this is added back in later
        RGUshV   = startV
        RGLshDAC = voltsToSHDAC(RGLshV, 49.9, 20)
        RGUshDAC = voltsToSHDAC(RGUshV, 49.9, 20)
        jy.do('wrebDAC.synchCommandLine(1000,"change rgLowSh %d")' % RGLshDAC)
        jy.do('wrebDAC.synchCommandLine(1000,"change rgHighSh %d")' % RGUshDAC)
        printv("-8V and 5V amplitude set  ")
        time.sleep(tsoak)
        # printv("RGLsh[V]: %5.2f   RGUsh[V]: %5.2f   RGLsh_DACval[ADU]: %4i   RGUsh_DACval[ADU]: %4i " % (RGLshV, RGUshV, RGLshDAC, RGUshDAC) )
        printv("RGLV[V]\tRGLV_DAC[ADU]\tRGUV[V]\tRGUV_DAC[ADU]\tWREB.RGL_V[V]\tWREB.RGU_V[V]")
        # Report arrays
        RGLV_arr       = []
        RGLdac_arr     = []
        RGUV_arr       = []
        RGUdac_arr     = []
        WREB_RGL_V_arr = []
        WREB_RGU_V_arr = []
        deltaRGLV_arr  = []
        deltaRGUV_arr  = []
        ClkHPS_I_arr   = []
        for RGDV in stepRange(0, amplitude, step):
            RGLV = startV - RGDV
            RGUV = startV + RGDV
            RGLdac = voltsToDAC(RGLV + amplitude, startV, 49.9, 20) # Add the amplitude back in
            RGUdac = voltsToDAC(RGUV, startV, 49.9, 20)
            printv("%5.2f\t%4i\t%5.2f\t%4i" % (RGLV, RGLdac, RGUV, RGUdac) ),
            jy.do('wrebDAC.synchCommandLine(1000,"change rgLow %d")' % RGLdac)
            jy.do('wrebDAC.synchCommandLine(1000,"change rgHigh %d")' % RGUdac)
            jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
            time.sleep(tsoak)
            WREB_RGL_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RGL_V").getResult()')
            WREB_RGU_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RGU_V").getResult()')
            ClkHPS_I = 0.1 * jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_I").getResult()')
            printv("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" % (WREB_RGL_V, WREB_RGU_V, (RGLV - WREB_RGL_V), (RGUV - WREB_RGU_V)) )
            # Append to arrays
            RGLV_arr       . append(RGLV)
            RGLdac_arr     . append(RGLdac)
            RGUV_arr       . append(RGUV)
            RGUdac_arr     . append(RGUdac)
            WREB_RGL_V_arr . append(WREB_RGL_V)
            WREB_RGU_V_arr . append(WREB_RGU_V)
            deltaRGLV_arr  . append(RGLV - WREB_RGL_V)
            deltaRGUV_arr  . append(RGUV - WREB_RGU_V)
            ClkHPS_I_arr   . append(ClkHPS_I)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((RGLV_arr, "RGLV (V)"),
                (RGUV_arr, "RGUV (V)"),
                (WREB_RGL_V_arr, "WREB.RGL_V (V)"),
                (WREB_RGU_V_arr, "WREB.RGU_V (V)"),
                (ClkHPS_I_arr, "ClkHPS_I (10mA)"))
        self.residuals = ((deltaRGLV_arr, "deltaRGLV (V)"),
                     (deltaRGUV_arr, "deltaRGUV (V)"))

        # Give pass/fail result
        self.passed  = "PASS"
        allowedError = 0.25 # Some arbitrary value giving the allowable residual error
        maxFails     = 4 # Some value giving the maximum number of allowed failures
        numErrors    = 0
        totalPoints  = 0
        for residual in deltaRGLV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1
        for residual in deltaRGUV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        ml, bl = np.polyfit(RGLV_arr, WREB_RGL_V_arr, 1)
        mu, bu = np.polyfit(RGUV_arr, WREB_RGU_V_arr, 1)
        self.stats  = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % \
            (ml, mu, totalPoints-numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(ml - 1.0) > 0.05 or abs(mu - 1.0) > 0.05:
            self.passed = "FAIL"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.makeResidualPlotPage("Diverging RGRails Test %i V" % self.startV,
                                 "tempFigures/divergingRGRails %i.jpg" % self.startV,
                                 self.data,
                                 self.residuals,
                                 pltRange = [-12, 12])
        pdf.cell(epw, pdf.font_size, self.stats, align = 'C', ln = 1)
        pdf.passFail(self.passed)
        pdf.columnTable(self.data + self.residuals)


class OGBias(object):
    def __init__(self):
        self.title = "OG Bias Test"
        pbar = progressbar("OG Bias Test, &count&: ", 21)
        if not verbose: pbar.start()
        printv("\nCCD bias OG voltage test ")
        OGshV = -5.0 # #sets the offset shift to -5V
        OGshDAC = voltsToSHDAC(OGshV, 10, 10)
        jy.do('wrebBias.synchCommandLine(1000,"change ogSh %d")' % OGshDAC)
        jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
        printv("VOGsh[V]: %5.2f   VOGsh_DACval[ADU]: %4i" % (OGshV, OGshDAC) )
        printv("VOG[V]   VOG_DACval[ADU]   WREB.OG[V]")
        OGV_arr       = []
        OGdac_arr     = []
        WREB_OG_V_arr = []
        deltaOGV_arr  = []
        for OGV in stepRange(OGshV, OGshV+10, 0.5):
            OGdac = voltsToDAC(OGV, OGshV, 10, 10)
            printv("%5.2f\t%4i" % (OGV, OGdac) ),
            jy.do('wrebBias.synchCommandLine(1000,"change og %d")' % OGdac)
            jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            WREB_OG_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OG_V").getResult()')
            printv("\t%5.2f\t\t%5.2f" % (WREB_OG_V, (OGV - WREB_OG_V)) )
            OGV_arr.append(OGV)
            OGdac_arr.append(OGdac)
            WREB_OG_V_arr.append(WREB_OG_V)
            deltaOGV_arr.append(OGV - WREB_OG_V)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((OGV_arr, "VOG (V)"),
                (WREB_OG_V_arr, "WREB.OG_V (V)"))
        self.residuals = ((deltaOGV_arr, "deltaVOG (V)"),)

        # Give pass/fail result
        self.passed  = "PASS"
        allowedError = 0.25 # Some arbitrary value giving the allowable residual error
        maxFails     = 2 # Some value giving the maximum number of allowed failures
        numErrors    = 0
        totalPoints  = 0
        for residual in deltaOGV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        m, b  = np.polyfit(OGV_arr, WREB_OG_V_arr, 1)
        self.stats = "Gain: %f.  %i/%i values okay." % (m, totalPoints-numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(m - 1.0) > 0.05:
            self.passed = "FAIL"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.residualTest(self.title, self.data, self.residuals, self.passed, self.stats)

class ODBias(object):
    def __init__(self):
        self.title = "OD Bias Test"
        pbar = progressbar("OD Bias Test, &count&: ", 21)
        if not verbose: pbar.start()
        printv("\nCCD bias OD voltage test ")
        printv("VOD[V]   VOD_DACval[ADU]   WREB.OD[V]")
        ODV_arr       = []
        ODdac_arr     = []
        WREB_OD_V_arr = []
        deltaODV_arr  = []
        for ODV in stepRange(0, 30, 2):
            ODdac = voltsToDAC(ODV, 0, 49.9, 10)
            printv("%5.2f\t%4i" % (ODV, ODdac)),
            jy.do('wrebBias.synchCommandLine(1000,"change od %d")' % ODdac)
            jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            WREB_OD_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_V").getResult()')
            printv("\t%5.2f\t\t%5.2f" % (WREB_OD_V,(ODV - WREB_OD_V)) )
            ODV_arr.append(ODV)
            ODdac_arr.append(ODdac)
            WREB_OD_V_arr.append(WREB_OD_V)
            deltaODV_arr.append(ODV - WREB_OD_V)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((ODV_arr, "VOD (V)"),
                (WREB_OD_V_arr, "WREB.OD_V (V)"))
        self.residuals = ((deltaODV_arr, "deltaVOD (V)"),)

        # Give pass/fail result
        self.passed       = "PASS"
        allowedError = 0.25 # Some arbitrary value giving the allowable residual error
        maxFails     = 2 # Some value giving the maximum number of allowed failures
        numErrors    = 0
        totalPoints  = 0
        for residual in deltaODV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        m, b  = np.polyfit(ODV_arr, WREB_OD_V_arr, 1)
        self.stats = "Gain: %f.  %i/%i values okay." % (m, totalPoints-numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(m - 1.0) > 0.05:
            self.passed = "FAIL"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.residualTest(self.title, self.data, self.residuals, self.passed, self.stats)

class GDBias(object):
    def __init__(self):
        self.title = "GD Bias Test"
        pbar = progressbar("GD Bias Test, &count&: ", 21)
        if not verbose: pbar.start()
        printv("\nCCD bias GD voltage test ")
        printv("VGD[V]   VGD_DACval[ADU]   WREB.GD[V]")
        GDV_arr       = []
        GDdac_arr     = []
        WREB_GD_V_arr = []
        deltaGDV_arr  = []
        for GDV in stepRange(0, 30, 2):
            GDdac = voltsToDAC(GDV, 0, 49.9, 10)
            printv("%5.2f\t%4i" % (GDV, GDdac)),
            jy.do('wrebBias.synchCommandLine(1000,"change gd %d")' % GDdac)
            jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            WREB_GD_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.GD_V").getResult()')
            printv("\t%5.2f\t\t%5.2f" % (WREB_GD_V,(GDV - WREB_GD_V)) )
            GDV_arr.append(GDV)
            GDdac_arr.append(GDdac)
            WREB_GD_V_arr.append(WREB_GD_V)
            deltaGDV_arr.append(GDV - WREB_GD_V)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((GDV_arr, "VGD (V)"),
                (WREB_GD_V_arr, "WREB.GD_V (V)"))
        self.residuals = ((deltaGDV_arr, "deltaVGD (V)"),)

        # Give pass/fail result
        self.passed       = "PASS"
        allowedError = 0.25 # Some arbitrary value giving the allowable residual error
        maxFails     = 2 # Some value giving the maximum number of allowed failures
        numErrors    = 0
        totalPoints  = 0
        for residual in deltaGDV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        m, b  = np.polyfit(GDV_arr, WREB_GD_V_arr, 1)
        self.stats = "Gain: %f.  %i/%i values okay." % (m, totalPoints-numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(m - 1.0) > 0.05:
            self.passed = "FAIL"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.residualTest(self.title, self.data, self.residuals, self.passed, self.stats)

class RDBias(object):
    def __init__(self):
        self.title = "RD Bias Test"
        pbar = progressbar("RD Bias Test, &count&: ", 21)
        if not verbose: pbar.start()
        printv("\nCCD bias RD voltage test ")
        printv("VRD[V]   VRD_DACval[ADU]   WREB.RD[V]")
        RDV_arr       = []
        RDdac_arr     = []
        WREB_RD_V_arr = []
        deltaRDV_arr  = []
        for RDV in stepRange(0, 30, 2):
            RDdac = voltsToDAC(RDV, 0, 49.9, 10)
            printv("%5.2f\t%4i" % (RDV, RDdac)),
            jy.do('wrebBias.synchCommandLine(1000,"change rd %d")' % RDdac)
            jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            WREB_RD_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RD_V").getResult()')
            printv("\t%5.2f\t\t%5.2f" % (WREB_RD_V, (RDV - WREB_RD_V)) )
            RDV_arr.append(RDV)
            RDdac_arr.append(RDdac)
            WREB_RD_V_arr.append(WREB_RD_V)
            deltaRDV_arr.append(RDV - WREB_RD_V)
            if not verbose: pbar.inc()
        if not verbose: pbar.finish()
        self.data = ((RDV_arr, "VRD (V)"),
                (WREB_RD_V_arr, "WREB.RD_V (V)"))
        self.residuals = ((deltaRDV_arr, "deltaVRD (V)"),)

        # Give pass/fail result
        self.passed       = "PASS"
        allowedError = 0.25 # Some arbitrary value giving the allowable residual error
        maxFails     = 2 # Some value giving the maximum number of allowed failures
        numErrors    = 0
        totalPoints  = 0
        for residual in deltaRDV_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        m, b  = np.polyfit(RDV_arr, WREB_RD_V_arr, 1)
        self.stats = "Gain: %f.  %i/%i values okay." % (m, totalPoints-numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(m - 1.0) > 0.05:
            self.passed = "FAIL"

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.residualTest(self.title, self.data, self.residuals, self.passed, self.stats)

class TemperatureLogging(object):
    def __init__(self, startTime):
        self.title = "Board Temperature"
        self.passed = "N/A"
        self.stats = "N/A"
        print ("Fetching temperature data...")
        now = int(time.time()*1000)
        os.system('cd TemperaturePlot/ && python refrigPlot.py . "prod" ccs-cr '+str(startTime)+' '+str(now))
        time.sleep(5)
        os.system("cd ..")

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.add_page()
        pdf.set_font('Arial', '', 12)
        pdf.set_fill_color(200, 220, 220)
        pdf.cell(0, 6, "Board temperature test", 0, 1, 'L', 1)
        # Make image
        width = .5 * (pdf.w - 2 * pdf.l_margin)
        height = pdf.h - 2 * pdf.t_margin
        # Board Temperatures
        imgListTemp = glob.glob("TemperaturePlot/WREB.Temp*.jpg")
        xhalf = (pdf.w - 2 * pdf.l_margin) / 2.0
        y0 = pdf.get_y()
        pdf.image(imgListTemp[0], x = pdf.l_margin, y = y0, w = width)
        pdf.image(imgListTemp[1], x = pdf.l_margin + xhalf, y = y0, w = width)
        pdf.image(imgListTemp[2], x = pdf.l_margin, y = y0 + height / 4, w = width)
        pdf.image(imgListTemp[3], x = pdf.l_margin + xhalf, y = y0 + height / 4, w = width)
        pdf.image(imgListTemp[4], x = pdf.l_margin, y = y0 + height / 2, w = width)
        pdf.image(imgListTemp[5], x = pdf.l_margin + xhalf, y = y0 + height / 2, w = width)
        # CCD Temperatures
        imgListCCDTemp = glob.glob("TemperaturePlot/WREB.CCDtemp*.jpg")
        imgListRTDTemp = glob.glob("TemperaturePlot/WREB.RTDtemp*.jpg")
        pdf.add_page()
        pdf.set_fill_color(200, 220, 220)
        pdf.cell(0, 6, "CCD temperature test", 0, 1, 'L', 1)
        y0 = pdf.get_y()
        pdf.image(imgListCCDTemp[0], x = pdf.l_margin, y = y0, w = width)
        pdf.image(imgListRTDTemp[0], x = pdf.l_margin + xhalf, y = y0, w = width)
        # Clean up
        for img in imgListTemp:
            os.remove(img)
        for img in imgListCCDTemp:
            os.remove(img)

class ASPICNoise(object):
    def __init__(self):
        '''Clamped/unclamped/reset noise distribution in ASPICs.'''
        self.title = "ASPIC Noise Tests"
        errorLevel = 5.5 # Max allowable standard deviation
        # Generate .fits image file
        if not os.path.exists("ASPICNoise"): os.makedirs("ASPICNoise")
        self.fnames = ["unclamped.fits", "clamped.fits", "reset.fits"]
        # categories = ["WREB_test_base_cfg",
        #               "WREB_test_clamped_cfg",
        #               "WREB_test_clamped_cfg"]
        categories = ["WREB_test_base_cfg",
                      "WREB_test_base_cfg",
                      "WREB_test_base_cfg"]
        sequencers = ["/u1/u/wreb/rafts/xml/wreb_ITL_20160419.seq",
                      "/u1/u/wreb/rafts/xml/wreb_ITL_20160419.seq",
                      "/u1/u/wreb/rafts/xml/wreb_ITL_20160419_aspic_reset.seq"]
        self.passed = "PASS"
        errCount = 0
        totalCount = 0
        for cat, seq, fname in zip(categories, sequencers, self.fnames):
            # Generate fits files to /u1/u/wreb/rafts/ASPICNoise
            commands = '''
            # Load standard sequencer and run it with 0s exposure time
            raftsub.synchCommandLine(1000,"loadCategories Rafts:{}")
            raftsub.synchCommandLine(1000, "loadSequencer {}")
            wreb.synchCommandLine(1000,"loadDacs true")
            wreb.synchCommandLine(1000,"loadBiasDacs true")
            wreb.synchCommandLine(1000,"loadAspics true")
            raftsub.synchCommandLine(1000, "setParameter Exptime 0");  # sets exposure time to 0ms
            time.sleep(tsoak)
            raftsub.synchCommandLine(1000, "startSequencer")
            time.sleep(2.5)  # takes 2 sec to read out
            raftsub.synchCommandLine(1000, "setFitsFileNamePattern {}")
            result = raftsub.synchCommand(1000,"saveFitsImage ASPICNoise")
            '''.format(cat, seq, fname)
            jy.do(textwrap.dedent(commands))
            print ("Generating test for %s..." % fname)
            time.sleep(5)
            # Read the data the plot
            f = fits.open("/u1/u/wreb/rafts/ASPICNoise/"+fname)
            # Set fonts
            font = {'family': 'normal',
                    'weight': 'bold',
                    'size'  : 8}
            matplotlib.rc('font', **font)
            # Generate the multiplot
            fig, axArr = plt.subplots(4, 4)
            fig.set_size_inches(8, 8)
            for i in range(16):
                totalCount += 1
                imgData = f[i + 1].data.flatten()
                subPlot = axArr[i / 4, i % 4]
                mu, sigma = np.mean(imgData), np.std(imgData)
                if sigma > errorLevel:
                    self.passed = "FAIL"
                    errCount += 1
                # Generate histogram
                n, bins, patches = subPlot.hist(imgData, 50, normed = 1, facecolor = 'green', alpha = 0.75)
                # Add a 'best fit' line
                y = matplotlib.mlab.normpdf(bins, mu, sigma)
                l = subPlot.plot(bins, y, 'r--', linewidth = 1)
                # Labeling
                # subPlot.set_xlabel('Pixel Value')
                # subPlot.set_ylabel('Normalized value')
                subPlot.set_yticklabels([])
                subPlot.set_title('Channel {}\n$\mu={:.2}, \sigma={:.2} $'.format(i + 1, mu, sigma))
                subPlot.grid(True)
            plt.tight_layout()
            plt.savefig("ASPICNoise/"+fname+".jpg")
            plt.close()
        self.stats = "{}/{} channels within sigma<{}.".format(errCount, totalCount, errorLevel)

    def summarize(self, summary):
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        pdf.addPlotPage("Unclamped ASPIC Noise Test", "ASPICNoise/" + self.fnames[0] + ".jpg")
        pdf.passFail(self.passed)
        pdf.addPlotPage("Clamped ASPIC Noise Test", "ASPICNoise/" + self.fnames[1] + ".jpg")
        pdf.passFail(self.passed)
        pdf.addPlotPage("Reset ASPIC Noise Test", "ASPICNoise/" + self.fnames[2] + ".jpg")
        pdf.passFail(self.passed)

class Summary(object):
    def __init__(self):
        self.testList = []
        self.passList = []
        self.statsList = []

class FunctionalTest(object):
    def __init__(self):
        self.summary = Summary()
        # Make temporary figure directory
        if not os.path.exists("tempFigures"): os.makedirs("tempFigures")
        # Execute desired tests
        print("\n\n\nWREB Functional Test:")
        self.tests = [IdleCurrentConsumption(),
                      ChannelTest(),
                      ASPICcommsTest(),
                      CSGate(),
                      PCKRails(),
                      SCKRails(),
                      RGRails(),
                      SCKRailsDiverging(9.0, 0.0),
                      SCKRailsDiverging(9.0, 3.0),
                      SCKRailsDiverging(9.0, -3.0),
                      RGRailsDiverging(9.0, 0.0),
                      RGRailsDiverging(9.0, 3.0),
                      RGRailsDiverging(9.0, -3.0),
                      OGBias(),
                      ODBias(),
                      GDBias(),
                      RDBias(),
                      TemperatureLogging(start),
                      ASPICNoise()]
        # self.tests = [idleCurrentConsumption(), ASPICNoise()]

    def generateReport(self):
        # Get hex board ID
        boardID = str(hex(int(
                jy.get('wreb.synchCommandLine(1000,"getSerialNumber").getResult()', dtype = "str").replace("L", ""))))
        # FPGA info in register 1
        FPGAInfo = jy.get('wreb.synchCommandLine(1000,"getRegister 1 1").getResult()', dtype = "str").split(": ")[1]

        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.set_font('Arial', '', 12)

        global epw # Constant: effective page width
        epw = pdf.w - 2 * pdf.l_margin

        # Generate summary page
        for test in self.tests:
            test.summarize(self.summary)
        pdf.summaryPage(boardID, FPGAInfo, self.summary.testList, self.summary.passList, self.summary.statsList)

        # Generate individual test reports
        for test in self.tests:
            test.report(pdf)

        if not args.noPDF:
            print("Generating PDF report at " + dataDir + '/WREBTest.pdf')
            pdf.output(dataDir + '/WREBTest.pdf', 'F')

        # Clean up
        shutil.rmtree("tempFigures")
        # shutil.rmtree("ASPICNoise")




# --------- Execution ---------
if __name__ == "__main__":
    # Argument parser
    import argparse
    parser = argparse.ArgumentParser(description =
        '''Test script for WREB controller boards to generate a pdf status report.''',
                                     epilog = '''>> Example: python WREBTest.py ~/u1/u/wreb/data -q''')
    parser.add_argument("writeDirectory", nargs = '?', default = "./Reports",
                        help="Directory to save outputs to. Defaults to ./Reports.", action="store")
    parser.add_argument("-v", "--verbose",
                        help="Print test results in the terminal.", action="store_true")
    parser.add_argument("-n", "--noPDF",
                        help="Do not render a PDF report for the tests.", action="store_true")
    args = parser.parse_args()


    tsoak   = 0.5
    dataDir = args.writeDirectory
    verbose = args.verbose

    jy = JythonInterface()
    jy.do('dataDir = %s'%args.writeDirectory)

    commands = '''
    from org.lsst.ccs.scripting import *
    import time
    import sys
    raftsub  = CCS.attachSubsystem("ccs-cr");
    wreb     = CCS.attachSubsystem("ccs-cr/WREB")
    wrebDAC  = CCS.attachSubsystem("ccs-cr/WREB.DAC")
    wrebBias = CCS.attachSubsystem("ccs-cr/WREB.Bias0")
    tsoak = 0.5
    # save config inside the board to temp_cfg and load the test_base_cfg
    raftsub.synchCommandLine(1000,"saveChangesForCategoriesAs Rafts:WREB_temp_cfg")
    raftsub.synchCommandLine(1000,"loadCategories Rafts:WREB_test_base_cfg")
    wreb.synchCommandLine(1000,"loadDacs true")
    wreb.synchCommandLine(1000,"loadBiasDacs true")
    wreb.synchCommandLine(1000,"loadAspics true")
    '''
    jy.do(textwrap.dedent(commands))

    # Run the tests, generate the report
    functionalTest = FunctionalTest()
    functionalTest.generateReport()

    # Restore previous settings and exit
    print ("WREB test completed.\n\n\n")
    exitScript()


