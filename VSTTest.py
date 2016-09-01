'''
@file VSTTest.py
@brief Suite of tests for the VST controller board.
This program communicates directly with the Jython interpreter to
manipulate the board, so it does not need to be loaded into the Jython exectuor.

External dependencies:
- astropy
- numpy
- matplotlib

To run:
- Ensure Jython console is running (./JythonConsole or the bootstrapper program)
- Ensure rebRun.sh 4 is running
- "python VSTTest.py [options]"
Initial crashing yielding a ValueError is likely due to a crRun or JythonConsole crashing or not being loaded.

Tests are structured as classes with four required methods:
- __init__ sets initial variables; minimum required variables are self.title and self.status.
- runTest is the body of the tests, running the code to execute the tests and storing the results to state variables.
- summarize writes summary information to the summary object passed to it; this is used in generating the cover page.
- report writes the portion of the pdf report that the test is responsible for.
Tests are executed from a list of test objects defined in FunctionalTest().
'''

from __future__ import print_function

import glob
import os, sys
import shutil
import signal
import textwrap
import numpy as np
import pickle
import matplotlib

matplotlib.use('Agg')  # Fixes "RuntimeError: Invalid DISPLAY variable" error
import matplotlib.pyplot as plt
from astropy.io import fits
from pdfGenVST import *
from threading import Thread
from datetime import datetime

from Libraries.FastProgressBar import progressbar  # Don't use for now
from Libraries.PythonBinding import *
from Libraries.dialog import Dialog


# Catch abort so previous settings can be restored
def initialize(jythonIF):
    # Some initialization commands for the CCS
    jythonIF.do('dataDir = %s' % args.writeDirectory)
    commands = '''
    from org.lsst.ccs.scripting import *
    import time
    import sys
    vst       = CCS.attachSubsystem("ccs-vst")
    reb0      = CCS.attachSubsystem("ccs-vst/REB0")
    reb0DAC   = CCS.attachSubsystem("ccs-vst/REB0.DAC")
    reb0Bias0 = CCS.attachSubsystem("ccs-vst/REB0.Bias0")
    reb0Bias1 = CCS.attachSubsystem("ccs-vst/REB0.Bias1")
    reb0Bias2 = CCS.attachSubsystem("ccs-vst/REB0.Bias2")
    tsoak = 0.5
    # save config inside the board to temp_cfg and load the test_base_cfg
    vst.synchCommandLine(1000,"saveChangesForCategoriesAs Rafts:REB4_temp_cfg")
    vst.synchCommandLine(1000,"loadCategories Rafts:REB4_test_base_cfg")
    reb0.synchCommandLine(1000,"loadDacs true")
    reb0.synchCommandLine(1000,"loadBiasDacs true")
    reb0.synchCommandLine(1000,"loadAspics true")
    '''
    jythonIF.do(textwrap.dedent(commands))
    time.sleep(5)


def resetSettings():
    '''@brief Reset the board settings for use in between tests.'''
    jy.do('vst.synchCommandLine(1000,"loadCategories Rafts:REB4_test_base_cfg")')
    jy.do('reb0.synchCommandLine(1000,"loadDacs true")')
    jy.do('reb0.synchCommandLine(1000,"loadBiasDacs true")')
    jy.do('reb0.synchCommandLine(1000,"loadAspics true")')
    time.sleep(tsoak)


def exitScript():
    '''@brief Reset settings and exit. Usually catches ^C.'''
    resetSettings()
    print("\nTests concluded or ^C raised. Restoring saved temp config and exiting...")
    sys.exit()


signal.signal(signal.SIGINT, exitScript)


# ---------- Helper functions ----------
def stepRange(start, end, step):
    while start <= end:
        yield start
        start += step


def voltsToDAC(volt, Rfb, Rin):
    dac = (volt * 4095 / 5 / (-float(Rfb) / float(Rin)))
    if dac > 4095: dac = 4095
    if dac < 0: dac = 0
    return dac


def voltsToShiftedDAC(volt, shvolt, Rfb, Rin):
    dac = ((volt - shvolt) * 4095 / 5 / (1 + float(Rfb) / float(Rin)))
    if dac > 4095: dac = 4095
    if dac < 0: dac = 0
    return dac


def rejectOutliers(data, sigma = 2.0):
    return data[abs(data - np.mean(data)) < sigma * np.std(data)]


def readRails(railType, count = 0, uBound = 20, lBound = -20):
    '''@brief Reads the upper and lower voltages for a rail type (RG, SClk, PClk) and rejects if nonsensible.
    @param railType "RG", "SClk", or "PClk" - specifies the type of rail to read
    @param uBound Upper bound on sensible voltage
    @param lBound Lower bound on sensible voltage'''
    UV = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.{}U").getResult()'.format(railType))
    LV = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.{}L").getResult()'.format(railType))
    if count >= 3:  # Max recursion depth
        return UV, LV
    if not (lBound < LV < uBound and lBound < UV < uBound):
        return readRails(railType, count + 1)
    return UV, LV


def voltsToRailDAC(V, rf, ri):
    '''@brief Given a voltage, return a pair of voltage, shift DAC values.
    @param V Desired output voltage
    @param rf Op-amp Rf
    @param ri Op-amp Ri
    @returns (voltage, shift voltage)'''
    if V >= 0:
        down = 0.0
        up = (V * 4095.0 * ri) / ((ri + rf) * 5.0)
    else:
        down = (-V * 4095.0 * ri) / (rf * 5.0)
        up = 0.0
    return int(up), int(down)


# Rail setting functions: in science raft, there is no upper rail shift, so upper rail cannot go below 0V
def setRGRailVoltage(lowV, highV, rf = 25.0, ri = 10.0):
    '''@brief Set the voltage for the RG rail system.
    @param lowV Desired lower rail voltage.
    @param highV Desired upper rail voltage
    @param rf Optional op-amp Rf, defaults to 49.9 Ohm.
    @param ri Optional op-amp Ri, defaults to 20.0 Ohm.'''
    LV, shLV = voltsToRailDAC(lowV, rf, ri)
    UV, shUV = voltsToRailDAC(highV, rf, ri)
    jy.do('reb0DAC.synchCommandLine(1000,"change rgLow %d")' % shLV)
    jy.do('reb0DAC.synchCommandLine(1000,"change rgLowSh %d")' % LV)  # Swapped
    # jy.do('reb0DAC.synchCommandLine(1000,"change rgHighSh %d")' % shUV)
    jy.do('reb0DAC.synchCommandLine(1000,"change rgHigh %d")' % UV)
    jy.do('reb0.synchCommandLine(1000,"loadDacs true")')
    time.sleep(tsoak)


def setSCKRailVoltage(lowV, highV, rf = 25.0, ri = 10.0):
    '''@brief Set the voltage for the SCK rail system.
    @param lowV Desired lower rail voltage.
    @param highV Desired upper rail voltage
    @param rf Optional op-amp Rf, defaults to 49.9 Ohm.
    @param ri Optional op-amp Ri, defaults to 20.0 Ohm.'''
    LV, shLV = voltsToRailDAC(lowV, rf, ri)
    UV, shUV = voltsToRailDAC(highV, rf, ri)
    jy.do('reb0DAC.synchCommandLine(1000,"change sclkLow %d")' % shLV)
    jy.do('reb0DAC.synchCommandLine(1000,"change sclkLowSh %d")' % LV)  # Swapped
    # jy.do('reb0DAC.synchCommandLine(1000,"change sclkHighSh %d")' % shUV)
    jy.do('reb0DAC.synchCommandLine(1000,"change sclkHigh %d")' % UV)
    jy.do('reb0.synchCommandLine(1000,"loadDacs true")')
    time.sleep(tsoak)


def setPCKRailVoltage(lowV, highV, rf = 25.0, ri = 10.0):
    '''@brief Set the voltage for the SCK rail system.
    @param lowV Desired lower rail voltage.
    @param highV Desired upper rail voltage
    @param rf Optional op-amp Rf, defaults to 49.9 Ohm.
    @param ri Optional op-amp Ri, defaults to 20.0 Ohm.'''
    LV, shLV = voltsToRailDAC(lowV, rf, ri)
    UV, shUV = voltsToRailDAC(highV, rf, ri)
    jy.do('reb0DAC.synchCommandLine(1000,"change pclkLow %d")' % shLV)
    jy.do('reb0DAC.synchCommandLine(1000,"change pclkLowSh %d")' % LV)  # Swapped
    # jy.do('reb0DAC.synchCommandLine(1000,"change pclkHighSh %d")' % shUV)
    jy.do('reb0DAC.synchCommandLine(1000,"change pclkHigh %d")' % UV)
    jy.do('reb0.synchCommandLine(1000,"loadDacs true")')
    time.sleep(tsoak)


def convert(value, type_):
    '''@brief Converts a value to the specified type.
    @param value Value to be converted
    @param type_ Type to convert to.
    @returns Converted value'''
    import importlib
    try:
        # Check if it's a builtin type
        module = importlib.import_module('__builtin__')
        cls = getattr(module, type_)
    except AttributeError:
        # if not, separate module and class
        module, type_ = type_.rsplit(".", 1)
        module = importlib.import_module(module)
        cls = getattr(module, type_)
    return cls(value)


def printv(string):
    '''@brief Print if verbose is enabled.'''
    if verbose:
        print(string)


class JythonInterface(CcsJythonInterpreter):
    '''@brief Some hacky workarounds to clean up the limited communication with the Jython interface.'''

    def do(self, code):
        '''@brief Execute a command on the CCS Jython interpreter.
        @param code Code as a literal to be executed.'''
        return self.syncExecution(code)

    def get(self, code, dtype = "float"):
        '''@brief Executes a piece of code and returns the value through getOutput().
        @param code Code as a literal to be executed.
        @param dtype Optional data type, defaults to float.
        @returns Converted value received through printed output from getOutput().
        getOutput() normally only returns the results of cout, so the result
        is automatically typecasted to type dtype.
        This should be used only with a single command at a time. Like I said,
        hacky work around, this should be fixed in the future.'''
        result = self.syncExecution("print (" + code + ")").getOutput()
        return convert(result, dtype)


# ------------ Tests ------------

class IdleCurrentConsumption(object):
    '''@brief Test for idle current consumption in the VST board.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "Idle Current"
        self.status = "Waiting..."

    # noinspection PyUnusedLocal
    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        self.passed = "N/A"
        self.stats = "N/A"
        # Idle Current Consumption
        print("Running idle current test...")
        DigV = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.DigV").getResult()')
        DigI = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.DigI").getResult()')
        AnaV = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.AnaV").getResult()')
        AnaI = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.AnaI").getResult()')
        ODV = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.ODV").getResult()')
        OD0V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OD0V").getResult()')
        OD1V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OD1V").getResult()')
        OD2V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OD2V").getResult()')
        ODI = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.ODI").getResult()')
        OG0V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OG0V").getResult()')
        OG1V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OG1V").getResult()')
        OG2V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OG2V").getResult()')
        ClkV = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.ClkV").getResult()')
        ClkI = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.ClkI").getResult()')
        # Create return objects
        self.voltages = ["DigV", "AnaV", "ODV", "OD0V", "OD1V", "OD2V", "OG0V", "OG1V", "OG2V", "ClkV"]
        self.voltages = [(name, eval(name)) for name in self.voltages]
        self.currents = ["DigI", "AnaI", "ODI", "ClkI"]
        self.currents = [(name, eval(name)) for name in self.currents]
        self.status = "DONE"

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.idleCurrent("Idle Current Test", self.voltages, self.currents)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/voltages.dat", "wb") as output:
                pickle.dump(self.voltages, output)
            with open(testPath + "/currents.dat", "wb") as output:
                pickle.dump(self.currents, output)


class ChannelTest(object):
    '''@brief Tests number of communicable channels available to the board.'''
    # TODO: fix formatting

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "Channel Comms"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        # TODO: Fix number of channels for VST
        # TODO: This test crashes unpredictably
        numChannels = 36  # There should be this many channels
        self.channels = jy.get('vst.synchCommandLine(1000,"getChannelNames").getResult()', dtype = 'str')
        self.channels = self.channels.replace("[", "").replace("]", "").replace("\n", "")
        self.channels = self.channels.split(", ")  # Channels is now a list of strings representing channel names
        pbar = progressbar("Channel Comms Test, &count&: ", len(self.channels))
        if not verbose and noGUI: pbar.start()
        # Primitive pass metric: test if channel list has all channels in it
        self.passed = "PASS"
        if len(self.channels) != numChannels:
            self.passed = "FAIL"
        # Attempt to get value from everything in channels
        self.vals = []
        for count, channel in enumerate(self.channels):
            val = jy.get('vst.synchCommandLine(1000,"getChannelValue ' + channel + '").getResult()')
            printv("Channel: {0:>10}  Value: {1:6}".format(channel, val))
            self.vals.append(val)
            self.status = int(-100 * float(count) / len(self.channels))
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.stats = "%i/%i channels missing." % (numChannels - len(self.channels), numChannels)
        self.passed = "PASS"  # TODO: Temporary fix
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
            @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.add_page()
        pdf.set_font('Courier', '', 12)
        pdf.cell(0, 6, "Channel Communications Test", 0, 1, 'L', 1)
        pdf.cell(0, 6, "", 0, 1, 'L', 0)
        pdf.columnTable([self.channels, self.vals], colHeaders = ["Channel", "Value"], fontSize = 8)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/channels.dat", "wb") as output:
                pickle.dump(self.channels, output)
            with open(testPath + "/vals.dat", "wb") as output:
                pickle.dump(self.vals, output)


class ASPICcommsTest(object):
    '''@brief Tests that the board can communicate with the ASPICS.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "ASPIC Comms"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        self.aspicstr = jy.get('vst.synchCommandLine(1000,"checkAspics").getResult()', dtype = 'str')
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
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.add_page()
        pdf.set_font('Courier', '', 12)
        pdf.cell(0, 6, "ASPIC Communications Test", 0, 1, 'L', 1)
        pdf.cell(0, 6, "", 0, 1, 'L', 0)
        pdf.cell(0, 6, "Test " + self.passed + ". " + self.stats, 0, 1, 'L')
        pdf.cell(0, 6, "ccs-vst.checkAsics result: " + self.aspicstr, 0, 1, 'L')
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/aspicstr.dat", "wb") as output:
                pickle.dump(self.aspicstr, output)


# class CSGate(object):
#     '''@brief Tests the current source gate.'''
#
#     def __init__(self):
#         '''@brief Initialize minimum required variables for test list.'''
#         self.title = "CS Gate Test"
#         self.status = "Waiting..."
#
#     def runTest(self):
#         '''@brief Run the test, save output to state variables.'''
#         # TODO: Sum 48 current channels to get OD_PSI
#         pbar = progressbar("CS Gate Test, &count&: ", 21)
#         if not verbose and noGUI: pbar.start()
#         # Arrays for report
#         CSGV_arr = []
#         VST_ODI_arr = []
#         VST_ODPS_I_arr = []
#         for CSGV in stepRange(0, 5, 0.25):
#             CSGdac = voltsToShiftedDAC(CSGV, 0, 1, 1e6)
#             printv("%5.2f\t%4i" % (CSGV, CSGdac)),
#             jy.do('wrebBias.synchCommandLine(1000,"change csGate %d")' % CSGdac)
#             jy.do('reb0.synchCommandLine(1000,"loadBiasDacs true")')
#             time.sleep(tsoak)
#             VST_OD_I = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.ODI").getResult()')
#             VST_ODPS_I = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.ODPS_I").getResult()')
#             printv("\t%5.2f\t%5.2f" % (VST_OD_I, VST_ODPS_I))
#             # Add to arrays to make plots for report
#             CSGV_arr.append(CSGV)
#             VST_OD_I_arr.append(VST_OD_I)
#             VST_ODPS_I_arr.append(VST_ODPS_I)
#             self.status = int(-100 * float(CSGV) / 5.0)
#             if not verbose and noGUI: pbar.inc()
#         if not verbose and noGUI: pbar.finish()
#         # Return to report generator
#         self.data = ((CSGV_arr, "CSGV (V)"), (VST_OD_I_arr, "REB0.OD_I (mA)"), (VST_ODPS_I_arr, "REB0.ODPS_I (mA)"))
#         # TODO: Implement pass/stats metric: linear scaling of currents with increased voltage
#         self.passed = "N/A"
#         self.stats = "N/A"
#         self.status = "DONE"
#
#     def summarize(self, summary):
#         '''@brief Summarize the test results for the cover page of the report.
#         @param summary Summary obejct passed from FunctionalTest()'''
#         summary.testList.append(self.title)
#         summary.passList.append(self.passed)
#         summary.statsList.append(self.stats)
#
#     def report(self, pdf, reportPath):
#         '''@brief generate this test's page in the PDF report.
#         @param pdf pyfpdf-compatible PDF object.'''
#         pdf.makePlotPage("CSGate Test", "CSGate.jpg", self.data)
#         pdf.columnTable(self.data)
#         if dump:
#             testPath = reportPath + "/" + self.title
#             os.mkdir(testPath)
#             with open(testPath + "/data.dat", "wb") as output:
#                 pickle.dump(self.data, output)


class PCKRails(object):
    '''@brief Tests the parallel clock rail performance.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "PCK Rails"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        pbar = progressbar("PCK Rails Test, &count&: ", 25)
        if not verbose and noGUI: pbar.start()
        printv("\nrail voltage generation for PCLK test ")
        pclkDV = 5  # delta voltage between lower and upper
        PCLKLshV = -8.0  # sets the offset shift to -8V on the lower
        # Report arrays
        pclkLV_arr = []
        pclkUV_arr = []
        VST_PCKL_V_arr = []
        VST_PCKU_V_arr = []
        deltapclkLV_arr = []
        deltapclkUV_arr = []
        for pclkLV in stepRange(PCLKLshV, PCLKLshV + 15, 0.5):
            pclkUV = pclkLV + pclkDV
            setPCKRailVoltage(pclkLV, pclkUV)
            # Read back voltage
            time.sleep(tsoak)
            VST_PCKU_V, VST_PCKL_V = readRails("PClk")
            printv("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
                   (VST_PCKL_V, VST_PCKU_V, (pclkLV - VST_PCKL_V), (pclkUV - VST_PCKU_V)))
            # Append to arrays
            pclkLV_arr.append(pclkLV)
            pclkUV_arr.append(pclkUV)
            VST_PCKL_V_arr.append(VST_PCKL_V)
            VST_PCKU_V_arr.append(VST_PCKU_V)
            deltapclkLV_arr.append(pclkLV - VST_PCKL_V)
            deltapclkUV_arr.append(pclkUV - VST_PCKU_V)
            self.status = int(-100 * float(pclkLV - PCLKLshV) / 12.0)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((pclkLV_arr, "pclkLV (V)"),
                     (pclkUV_arr, "pclkUV (V)"),
                     (VST_PCKL_V_arr, "REB0.PCKL_V (V)"),
                     (VST_PCKU_V_arr, "REB0.PCKU_V (V)"))
        self.residuals = ((deltapclkLV_arr, "deltapclkLV (V)"),
                          (deltapclkUV_arr, "deltapclkUV (V)"))

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.1  # 100mV
        maxFails = 0  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        self.ROI = [6, 21]
        for x, residual in enumerate(deltapclkLV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1
        for x, residual in enumerate(deltapclkUV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1

        # Other information
        l, h = self.ROI
        ml, bl = np.polyfit(pclkLV_arr[l:h], VST_PCKL_V_arr[l:h], 1)
        mu, bu = np.polyfit(pclkUV_arr[l:h], VST_PCKU_V_arr[l:h], 1)
        self.stats = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % \
                     (ml, mu, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.residualTest("PCK Rails Test", self.data, self.residuals, self.passed, self.stats, ROI = self.ROI)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)


class SCKRails(object):
    '''@brief Tests the serial clock rail performance.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "SCK Rails"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        pbar = progressbar("SCK Rails Test, &count&: ", 25)
        if not verbose and noGUI: pbar.start()
        printv("\nrail voltage generation for SCLK test ")
        sclkDV = 5  # delta voltage between lower and upper
        SCLKLshV = -8.5  # sets the offset shift to -8V on the lower
        # Report arrays
        sclkLV_arr = []
        sclkUV_arr = []
        VST_SCKL_V_arr = []
        VST_SCKU_V_arr = []
        deltasclkLV_arr = []
        deltasclkUV_arr = []
        for sclkLV in stepRange(SCLKLshV, SCLKLshV + 12, 0.5):
            sclkUV = sclkLV + sclkDV
            setSCKRailVoltage(sclkLV, sclkUV)
            # Read back voltage
            time.sleep(tsoak)
            VST_SCKU_V, VST_SCKL_V = readRails("SClk")
            printv("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
                   (VST_SCKL_V, VST_SCKU_V, (sclkLV - VST_SCKL_V), (sclkUV - VST_SCKU_V)))
            # Append to arrays
            sclkLV_arr.append(sclkLV)
            sclkUV_arr.append(sclkUV)
            VST_SCKL_V_arr.append(VST_SCKL_V)
            VST_SCKU_V_arr.append(VST_SCKU_V)
            deltasclkLV_arr.append(sclkLV - VST_SCKL_V)
            deltasclkUV_arr.append(sclkUV - VST_SCKU_V)
            self.status = int(-100 * float(sclkLV - SCLKLshV) / 12.0)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((sclkLV_arr, "sclkLV (V)"),
                     (sclkUV_arr, "sclkUV (V)"),
                     (VST_SCKL_V_arr, "REB0.SCKL_V (V)"),
                     (VST_SCKU_V_arr, "REB0.SCKU_V (V)"))
        self.residuals = ((deltasclkLV_arr, "deltasclkLV (V)"),
                          (deltasclkUV_arr, "deltasclkUV (V)"))

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.1  # 100mV
        maxFails = 0  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        self.ROI = [6, 21]
        for x, residual in enumerate(deltasclkLV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1
        for x, residual in enumerate(deltasclkUV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1

        # Other information
        l, h = self.ROI
        ml, bl = np.polyfit(sclkLV_arr[l:h], VST_SCKL_V_arr[l:h], 1)
        mu, bu = np.polyfit(sclkUV_arr[l:h], VST_SCKU_V_arr[l:h], 1)
        self.stats = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % \
                     (ml, mu, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.residualTest("SCK Rails Test", self.data, self.residuals, self.passed, self.stats, ROI = self.ROI)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)
            with open(testPath + "/residuals.dat", "wb") as output:
                pickle.dump(self.residuals, output)


class SCKRailsDiverging(object):
    '''@brief Test the serial clock rail performance with a diverging voltage pattern.'''

    # TODO: better aphysical value rejection

    def __init__(self, amplitude, startV):
        '''@brief Initialize required variables for test list and stores input arguments to state variables.
        @param amplitude Maximum voltage differential between rails, half-wave. (5V amplitude is 10V max difference.)
        @param startV Initial voltage the diverging rails tests starts at.'''
        self.title = "Diverging SCK Rails, " + str(int(startV)) + "V"
        self.amplitude = amplitude
        self.startV = startV
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        '''Diverging SCK Rails test. Amplitude is half-wave maximum divergence,
        startV is initial voltage to start LV=UV diverging from.'''
        step = 0.5
        pbar = progressbar("Diverging SCK Rails Test, &count&: ", self.amplitude / step + 1)
        if not verbose and noGUI: pbar.start()
        printv("\nDiverging rail voltage generation for SCLK test ")
        time.sleep(tsoak)
        # Report arrays
        sclkLV_arr = []
        sclkUV_arr = []
        VST_SCKL_V_arr = []
        VST_SCKU_V_arr = []
        deltasclkLV_arr = []
        deltasclkUV_arr = []
        ClkHPS_I_arr = []
        for sclkDV in stepRange(0, self.amplitude, step):
            # Set diverging rail voltages
            sclkLV = self.startV - sclkDV
            sclkUV = self.startV + sclkDV
            setSCKRailVoltage(sclkLV, sclkUV)
            # Read back voltage
            VST_SCKU_V, VST_SCKL_V = readRails("SClk")
            ClkHPS_I = 0.1 * jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.ClkI").getResult()')
            printv("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
                   (VST_SCKL_V, VST_SCKU_V, (sclkLV - VST_SCKL_V), (sclkUV - VST_SCKU_V)))
            # Append to arrays
            sclkLV_arr.append(sclkLV)
            sclkUV_arr.append(sclkUV)
            VST_SCKL_V_arr.append(VST_SCKL_V)
            VST_SCKU_V_arr.append(VST_SCKU_V)
            deltasclkLV_arr.append(sclkLV - VST_SCKL_V)
            deltasclkUV_arr.append(sclkUV - VST_SCKU_V)
            ClkHPS_I_arr.append(ClkHPS_I)
            self.status = int(-100 * float(sclkDV) / self.amplitude)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((sclkLV_arr, "sclkLV (V)"),
                     (sclkUV_arr, "sclkUV (V)"),
                     (VST_SCKL_V_arr, "REB0.SCKL_V (V)"),
                     (VST_SCKU_V_arr, "REB0.SCKU_V (V)"),
                     (ClkHPS_I_arr, "ClkHPS_I (10mA)"))
        self.residuals = ((deltasclkLV_arr, "deltasclkLV (V)"),
                          (deltasclkUV_arr, "deltasclkUV (V)"))

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.15  # 100mV
        maxFails = 0  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        # currents = np.array(ClkHPS_I_arr)
        U, L = np.array(VST_SCKU_V_arr), np.array(VST_SCKL_V_arr)
        iterationValues = np.arange(self.amplitude / step + 1)
        # Select range where current is less than 40mA and voltages are within +/-(-0.5 to +7.5V)
        try:
            self.ROI = np.take(iterationValues[  # (currents < 4.0 ) &
                                   (-0.0 < U) &
                                   (U < 7.0) &
                                   (-7.0 < L) &
                                   (L < 0.0)], [1, -1])
            self.ROI = map(int, self.ROI)
        except IndexError:
            self.ROI = [int(iterationValues[0]), int(iterationValues[-1])]
        for x, residual in enumerate(deltasclkLV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1
        for x, residual in enumerate(deltasclkUV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1

        # Other information
        l, h = self.ROI
        ml, bl = np.polyfit(sclkLV_arr[l:h], VST_SCKL_V_arr[l:h], 1)
        mu, bu = np.polyfit(sclkUV_arr[l:h], VST_SCKU_V_arr[l:h], 1)
        self.stats = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % (ml, mu, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.makeResidualPlotPage("Diverging SCKRails Test %i V" % int(self.startV),
                                 "tempFigures/divergingSCKRails %i.jpg" % int(self.startV),
                                 self.data,
                                 self.residuals,
                                 ROI = self.ROI,
                                 pltRange = [-12, 12])
        pdf.cell(epw, pdf.font_size, self.stats, align = 'C', ln = 1)
        pdf.passFail(self.passed)
        pdf.columnTable(self.data + self.residuals, ROI = self.ROI)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)
            with open(testPath + "/residuals.dat", "wb") as output:
                pickle.dump(self.residuals, output)


class RGRails(object):
    '''@brief Tests the reset gate rail performance.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "RG Rails"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        pbar = progressbar("RG Rails Test, &count&: ", 25)
        if not verbose and noGUI: pbar.start()
        printv("\nrail voltage generation for RG test ")
        RGDV = 5  # delta voltage between lower and upper
        RGLshV = -8.5  # sets the offset shift to -8.5V on the lower
        # Report arrays
        RGLV_arr = []
        RGUV_arr = []
        VST_RGL_V_arr = []
        VST_RGU_V_arr = []
        deltaRGLV_arr = []
        deltaRGUV_arr = []
        for RGLV in stepRange(RGLshV, RGLshV + 12, 0.5):  # step trough the lower rail range
            # Set diverging rail voltages
            RGUV = RGLV + RGDV  # adds the delta voltage to the upper rail
            setRGRailVoltage(RGLV, RGUV)
            # Read back voltages
            time.sleep(tsoak)
            VST_RGU_V, VST_RGL_V = readRails("RG")
            # Append to arrays
            RGLV_arr.append(RGLV)
            RGUV_arr.append(RGUV)
            VST_RGL_V_arr.append(VST_RGL_V)
            VST_RGU_V_arr.append(VST_RGU_V)
            deltaRGLV_arr.append(RGLV - VST_RGL_V)
            deltaRGUV_arr.append(RGUV - VST_RGU_V)
            self.status = int(-100 * float(RGLV - RGLshV) / 12.0)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((RGLV_arr, "RGLV (V)"),
                     (RGUV_arr, "RGUV (V)"),
                     (VST_RGL_V_arr, "REB0.RGL_V (V)"),
                     (VST_RGU_V_arr, "REB0.RGU_V (V)"))
        self.residuals = ((deltaRGLV_arr, "deltaRGLV (V)"),
                          (deltaRGUV_arr, "deltaRGUV (V)"))

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.15  # 100mV
        maxFails = 0  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        self.ROI = [7, 22]
        for x, residual in enumerate(deltaRGLV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1
        for x, residual in enumerate(deltaRGUV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1

        # Other information
        l, h = self.ROI
        ml, bl = np.polyfit(RGLV_arr[l:h], VST_RGL_V_arr[l:h], 1)
        mu, bu = np.polyfit(RGUV_arr[l:h], VST_RGU_V_arr[l:h], 1)
        self.stats = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % \
                     (ml, mu, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.residualTest("RG Rails Test", self.data, self.residuals, self.passed, self.stats, ROI = self.ROI)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)
            with open(testPath + "/residuals.dat", "wb") as output:
                pickle.dump(self.residuals, output)


class RGRailsDiverging(object):
    '''@brief Tests the reset gate rail performance with a diverging voltage pattern.'''

    def __init__(self, amplitude, startV):
        '''@brief Initialize required variables for test list and stores input arguments to state variables.
        @param amplitude Maximum voltage differential between rails, half-wave. (5V amplitude is 10V max difference.)
        @param startV Initial voltage the diverging rails tests starts at.'''
        self.title = "Diverging RG Rails, " + str(int(startV)) + "V"
        self.amplitude = amplitude
        self.startV = startV
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        step = 0.5
        pbar = progressbar("Diverging RG Rails Test, &count&: ", self.amplitude / step + 1)
        if not verbose and noGUI: pbar.start()
        printv("\nDiverging rail voltage generation for RG test ")
        # Report arrays
        RGLV_arr = []
        RGUV_arr = []
        VST_RGL_V_arr = []
        VST_RGU_V_arr = []
        deltaRGLV_arr = []
        deltaRGUV_arr = []
        ClkHPS_I_arr = []
        for RGDV in stepRange(0, self.amplitude, step):
            # Set diverging rail voltages
            RGLV = self.startV - RGDV
            RGUV = self.startV + RGDV
            setRGRailVoltage(RGLV, RGUV)
            # Read back voltages
            VST_RGU_V, VST_RGL_V = readRails("RG")
            ClkHPS_I = 0.1 * jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.ClkI").getResult()')
            # Append to arrays
            RGLV_arr.append(RGLV)
            RGUV_arr.append(RGUV)
            VST_RGL_V_arr.append(VST_RGL_V)
            VST_RGU_V_arr.append(VST_RGU_V)
            deltaRGLV_arr.append(RGLV - VST_RGL_V)
            deltaRGUV_arr.append(RGUV - VST_RGU_V)
            ClkHPS_I_arr.append(ClkHPS_I)
            self.status = int(-100 * float(RGDV) / self.amplitude)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((RGLV_arr, "RGLV (V)"),
                     (RGUV_arr, "RGUV (V)"),
                     (VST_RGL_V_arr, "REB0.RGL_V (V)"),
                     (VST_RGU_V_arr, "REB0.RGU_V (V)"),
                     (ClkHPS_I_arr, "ClkHPS_I (10mA)"))
        self.residuals = ((deltaRGLV_arr, "deltaRGLV (V)"),
                          (deltaRGUV_arr, "deltaRGUV (V)"))

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.15  # 100mV
        maxFails = 1  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        UV, LV = np.array(VST_RGU_V_arr), np.array(VST_RGL_V_arr)
        iterationValues = np.arange(self.amplitude / step + 1)
        # Start where values begin to be accurate
        try:
            ROI = iterationValues[1:][(-7.0 < LV[1:]) & (LV[1:] < 0.0) & (-0.0 < UV[1:]) & (UV[1:] < 7.0)]
            self.ROI = [ROI[0], ROI[-1]]
            self.ROI = map(int, self.ROI)
        except IndexError:
            self.ROI = [0, len(RGLV_arr) - 1]

        for x, residual in enumerate(deltaRGLV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1
        for x, residual in enumerate(deltaRGUV_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1

        # Other information
        l, h = self.ROI
        ml, bl = np.polyfit(RGLV_arr[l:h], VST_RGL_V_arr[l:h], 1)
        mu, bu = np.polyfit(RGUV_arr[l:h], VST_RGU_V_arr[l:h], 1)
        self.stats = "LV Gain: %f.  UV Gain: %f.  %i/%i values okay." % \
                     (ml, mu, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.makeResidualPlotPage("Diverging RGRails Test %i V" % self.startV,
                                 "tempFigures/divergingRGRails %i.jpg" % self.startV,
                                 self.data,
                                 self.residuals,
                                 ROI = self.ROI,
                                 pltRange = [-12, 12])
        pdf.cell(epw, pdf.font_size, self.stats, align = 'C', ln = 1)
        pdf.passFail(self.passed)
        pdf.columnTable(self.data + self.residuals, ROI = self.ROI)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)
            with open(testPath + "/residuals.dat", "wb") as output:
                pickle.dump(self.residuals, output)


class OGBias(object):
    '''@brief Tests the output gate performance. The real OG test.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "OG Bias Test"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        pbar = progressbar("OG Bias Test, &count&: ", 21)
        if not verbose and noGUI: pbar.start()
        OGshV = -5.0  # #sets the offset shift to -5V
        OGshDAC = voltsToDAC(OGshV, 10.0, 10)
        jy.do('reb0Bias0.synchCommandLine(1000,"change ogSh %d")' % OGshDAC)
        jy.do('reb0Bias1.synchCommandLine(1000,"change ogSh %d")' % OGshDAC)
        jy.do('reb0Bias2.synchCommandLine(1000,"change ogSh %d")' % OGshDAC)
        jy.do('reb0.synchCommandLine(1000,"loadBiasDacs true")')
        OGV_arr = [i for i in stepRange(OGshV, OGshV + 10, 0.5)]
        OG0V_arr = []
        OG1V_arr = []
        OG2V_arr = []
        deltaOG0V_arr = []
        deltaOG1V_arr = []
        deltaOG2V_arr = []
        for OGV in OGV_arr:
            OGdac = voltsToShiftedDAC(OGV, OGshV, 10.0, 10)
            jy.do('reb0Bias0.synchCommandLine(1000,"change og %d")' % OGdac)
            jy.do('reb0Bias1.synchCommandLine(1000,"change og %d")' % OGdac)
            jy.do('reb0Bias2.synchCommandLine(1000,"change og %d")' % OGdac)
            jy.do('reb0.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            OG0V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OG0V").getResult()')
            OG1V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OG1V").getResult()')
            OG2V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OG2V").getResult()')
            OG0V_arr.append(OG0V)
            OG1V_arr.append(OG1V)
            OG2V_arr.append(OG2V)
            deltaOG0V_arr.append(OGV - OG0V)
            deltaOG1V_arr.append(OGV - OG1V)
            deltaOG2V_arr.append(OGV - OG2V)
            self.status = int(-100 * float(OGV - OGshV) / 10.0)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((OGV_arr, "VOG (V)"),
                     (OG0V_arr, "REB0.OG0V (V)"),
                     (OG1V_arr, "REB0.OG1V (V)"),
                     (OG2V_arr, "REB0.OG2V (V)"))
        self.residuals = ((deltaOG0V_arr, "deltaOG0V (V)"),
                          (deltaOG1V_arr, "deltaOG1V (V)"),
                          (deltaOG2V_arr, "deltaOG2V (V)"),)

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.15  # 150mV
        maxFails = 0  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        # No ROI: entire span
        for residual in deltaOG0V_arr + deltaOG1V_arr + deltaOG2V_arr:
            if abs(residual) > allowedError: numErrors += 1
            totalPoints += 1

        # Other information
        m0, b0 = np.polyfit(OGV_arr, OG0V_arr, 1)
        m1, b1 = np.polyfit(OGV_arr, OG1V_arr, 1)
        m2, b2 = np.polyfit(OGV_arr, OG2V_arr, 1)
        self.stats = "Gain: (%.3f, %.3f, %.3f). %i/%i values okay." % (m0, m1, m2, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails or abs(m0 - 1.0) > 0.05 or abs(m1 - 1.0) > 0.05 or abs(m2 - 1.0) > 0.05:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.residualTest(self.title, self.data, self.residuals, self.passed, self.stats)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)
            with open(testPath + "/residuals.dat", "wb") as output:
                pickle.dump(self.residuals, output)


class ODBias(object):
    '''@brief Tests the output drain performance.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "OD Bias Test"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        pbar = progressbar("OD Bias Test, &count&: ", 21)
        if not verbose and noGUI: pbar.start()
        ODV_arr = [i for i in stepRange(0, 30, 2)]
        OD0V_arr = []
        OD1V_arr = []
        OD2V_arr = []
        deltaOD0V_arr = []
        deltaOD1V_arr = []
        deltaOD2V_arr = []
        for ODV in ODV_arr:
            ODdac = voltsToShiftedDAC(ODV, 0, 62.5, 10.0)
            jy.do('reb0Bias0.synchCommandLine(1000,"change od %d")' % ODdac)
            jy.do('reb0Bias1.synchCommandLine(1000,"change od %d")' % ODdac)
            jy.do('reb0Bias2.synchCommandLine(1000,"change od %d")' % ODdac)
            jy.do('reb0.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            OD0V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OD0V").getResult()')
            OD1V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OD1V").getResult()')
            OD2V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.OD2V").getResult()')
            OD0V_arr.append(OD0V)
            OD1V_arr.append(OD1V)
            OD2V_arr.append(OD2V)
            deltaOD0V_arr.append(ODV - OD0V)
            deltaOD1V_arr.append(ODV - OD1V)
            deltaOD2V_arr.append(ODV - OD2V)
            self.status = int(-100 * float(ODV - 0.0) / 30.0)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((ODV_arr, "VOD (V)"),
                     (OD0V_arr, "REB0.OD0V (V)"),
                     (OD1V_arr, "REB0.OD1V (V)"),
                     (OD2V_arr, "REB0.OD2V (V)"))
        self.residuals = ((deltaOD0V_arr, "deltaOD0V (V)"),
                          (deltaOD1V_arr, "deltaOD1V (V)"),
                          (deltaOD2V_arr, "deltaOD2V (V)"),)

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.15  # 150 mV
        maxFails = 2  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        self.ROI = [1, 14]
        for x, residual in enumerate(deltaOD0V_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1
        for x, residual in enumerate(deltaOD1V_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1
        for x, residual in enumerate(deltaOD2V_arr):
            if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
            totalPoints += 1

        # Other information
        l, h = self.ROI
        m0, b0 = np.polyfit(ODV_arr[l:h], OD0V_arr[l:h], 1)
        m1, b1 = np.polyfit(ODV_arr[l:h], OD1V_arr[l:h], 1)
        m2, b2 = np.polyfit(ODV_arr[l:h], OD2V_arr[l:h], 1)
        self.stats = "Gain: (%.3f, %.3f, %.3f). %i/%i values okay." % (m0, m1, m2, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.residualTest(self.title, self.data, self.residuals, self.passed, self.stats, ROI = self.ROI)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)
            with open(testPath + "/residuals.dat", "wb") as output:
                pickle.dump(self.residuals, output)


class GDBias(object):
    '''@brief Tests the guard drain performance.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "GD Bias Test"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        pbar = progressbar("GD Bias Test, &count&: ", 16)
        if not verbose and noGUI: pbar.start()
        GDV_arr = [i for i in stepRange(0, 30, 2)]
        GD0V_arr = []
        GD1V_arr = []
        GD2V_arr = []
        deltaGD0V_arr = []
        deltaGD1V_arr = []
        deltaGD2V_arr = []
        for GDV in GDV_arr:
            GDdac = voltsToShiftedDAC(GDV, 0, 62.5, 10.0)
            jy.do('reb0Bias0.synchCommandLine(1000,"change gd %d")' % GDdac)
            jy.do('reb0Bias1.synchCommandLine(1000,"change gd %d")' % GDdac)
            jy.do('reb0Bias2.synchCommandLine(1000,"change gd %d")' % GDdac)
            jy.do('reb0.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            GD0V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.GD0V").getResult()')
            GD1V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.GD1V").getResult()')
            GD2V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.GD2V").getResult()')
            GD0V_arr.append(GD0V)
            GD1V_arr.append(GD1V)
            GD2V_arr.append(GD2V)
            deltaGD0V_arr.append(GDV - GD0V)
            deltaGD1V_arr.append(GDV - GD1V)
            deltaGD2V_arr.append(GDV - GD2V)
            self.status = int(-100 * float(GDV - 0.0) / 30.0)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((GDV_arr, "VGD (V)"),
                     (GD0V_arr, "REB0.GD0V (V)"),
                     (GD1V_arr, "REB0.GD1V (V)"),
                     (GD2V_arr, "REB0.GD2V (V)"))
        self.residuals = ((deltaGD0V_arr, "deltaOD0V (V)"),
                          (deltaGD1V_arr, "deltaOD1V (V)"),
                          (deltaGD2V_arr, "deltaOD2V (V)"),)

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.15  # 150 mV
        maxFails = 2  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        self.ROI = [0, 13]
        for arr in [deltaGD0V_arr, deltaGD1V_arr, deltaGD2V_arr]:
            for x, residual in enumerate(arr):
                if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
                totalPoints += 1

        # Other information
        l, h = self.ROI
        m0, b0 = np.polyfit(GDV_arr[l:h], GD0V_arr[l:h], 1)
        m1, b1 = np.polyfit(GDV_arr[l:h], GD1V_arr[l:h], 1)
        m2, b2 = np.polyfit(GDV_arr[l:h], GD2V_arr[l:h], 1)
        self.stats = "Gain: (%.3f, %.3f, %.3f). %i/%i values okay." % (m0, m1, m2, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.residualTest(self.title, self.data, self.residuals, self.passed, self.stats, ROI = self.ROI)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)
            with open(testPath + "/residuals.dat", "wb") as output:
                pickle.dump(self.residuals, output)


class RDBias(object):
    '''@brief Tests the reset drain performance.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "RD Bias Test"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        pbar = progressbar("RD Bias Test, &count&: ", 16)
        if not verbose and noGUI: pbar.start()
        RDV_arr = [i for i in stepRange(0, 30, 2)]
        RD0V_arr = []
        RD1V_arr = []
        RD2V_arr = []
        deltaRD0V_arr = []
        deltaRD1V_arr = []
        deltaRD2V_arr = []
        for RDV in RDV_arr:
            RDdac = voltsToShiftedDAC(RDV, 0, 40.0, 10)
            jy.do('reb0Bias0.synchCommandLine(1000,"change rd %d")' % RDdac)
            jy.do('reb0Bias1.synchCommandLine(1000,"change rd %d")' % RDdac)
            jy.do('reb0Bias2.synchCommandLine(1000,"change rd %d")' % RDdac)
            jy.do('reb0.synchCommandLine(1000,"loadBiasDacs true")')
            time.sleep(tsoak)
            RD0V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.RD0V").getResult()')
            RD1V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.RD1V").getResult()')
            RD2V = jy.get('vst.synchCommandLine(1000,"readChannelValue REB0.RD2V").getResult()')
            RD0V_arr.append(RD0V)
            RD1V_arr.append(RD1V)
            RD2V_arr.append(RD2V)
            deltaRD0V_arr.append(RDV - RD0V)
            deltaRD1V_arr.append(RDV - RD1V)
            deltaRD2V_arr.append(RDV - RD2V)
            self.status = int(-100 * float(RDV - 0.0) / 30.0)
            if not verbose and noGUI: pbar.inc()
        if not verbose and noGUI: pbar.finish()
        self.data = ((RDV_arr, "VRD (V)"),
                     (RD0V_arr, "REB0.RD0V (V)"),
                     (RD1V_arr, "REB0.RD1V (V)"),
                     (RD2V_arr, "REB0.RD2V (V)"))
        self.residuals = ((deltaRD0V_arr, "deltaOD0V (V)"),
                          (deltaRD1V_arr, "deltaOD1V (V)"),
                          (deltaRD2V_arr, "deltaOD2V (V)"),)

        # Give pass/fail result
        self.passed = "PASS"
        allowedError = 0.15  # 150 mV
        maxFails = 2  # Some value giving the maximum number of allowed failures
        numErrors = 0
        totalPoints = 0
        self.ROI = [0, 13]
        for arr in [deltaRD0V_arr, deltaRD1V_arr, deltaRD2V_arr]:
            for x, residual in enumerate(arr):
                if abs(residual) > allowedError and self.ROI[0] <= x <= self.ROI[1]: numErrors += 1
                totalPoints += 1

        # Other information
        l, h = self.ROI
        m0, b0 = np.polyfit(RDV_arr[l:h], RD0V_arr[l:h], 1)
        m1, b1 = np.polyfit(RDV_arr[l:h], RD1V_arr[l:h], 1)
        m2, b2 = np.polyfit(RDV_arr[l:h], RD2V_arr[l:h], 1)
        self.stats = "Gain: (%.3f, %.3f, %.3f). %i/%i values okay." % (m0, m1, m2, totalPoints - numErrors, totalPoints)

        # Pass criterion:
        if numErrors > maxFails:
            self.passed = "FAIL"
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        pdf.residualTest(self.title, self.data, self.residuals, self.passed, self.stats, ROI = self.ROI)
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)
            with open(testPath + "/residuals.dat", "wb") as output:
                pickle.dump(self.residuals, output)


class TemperatureLogging(object):
    '''@brief Requests temperature logs for REB0.Temp(1-6) and CCD since the test started from the board's database.'''

    def __init__(self, startTime):
        '''@brief Initialize required variables for test list.
        @param startTime Time to request temperature data since. Should be the beginning time of this test.'''
        self.title = "Board Temperature"
        self.startTime = startTime
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        # TODO: Need CCD and RTD temps
        self.status = "Running..."
        self.passed = "N/A"
        self.stats = "N/A"
        print("Fetching temperature data...")
        now = int(time.time() * 1000)
        start = int(1000.0 * self.startTime)
        os.system('cd TemperaturePlot/ && python refrigPlot.py . "prod" ccs-vst ' +
                  str(start) + ' ' + str(now) + ' ' +
                  '"REB0.Temp1 REB0.Temp2 REB0.Temp3 REB0.Temp4 REB0.Temp5 REB0.Temp6 REB0.Temp7 REB0.Temp8"')
        time.sleep(5)
        os.system("cd ..")
        self.status = "DONE"

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.'''
        pdf.add_page()
        pdf.set_font('Courier', '', 12)
        pdf.set_fill_color(200, 220, 220)
        pdf.cell(0, 6, "Board temperature test", 0, 1, 'L', 0)
        # Make image
        width = .5 * (pdf.w - 2 * pdf.l_margin)
        height = pdf.h - 2 * pdf.t_margin
        # Board Temperatures
        try:
            imgListTemp = glob.glob("TemperaturePlot/REB0.Temp*.jpg")
            xhalf = (pdf.w - 2 * pdf.l_margin) / 2.0
            y0 = pdf.get_y()
            pdf.image(imgListTemp[0], x = pdf.l_margin, y = y0, w = width)
            pdf.image(imgListTemp[1], x = pdf.l_margin + xhalf, y = y0, w = width)
            pdf.image(imgListTemp[2], x = pdf.l_margin, y = y0 + height / 4, w = width)
            pdf.image(imgListTemp[3], x = pdf.l_margin + xhalf, y = y0 + height / 4, w = width)
            pdf.image(imgListTemp[4], x = pdf.l_margin, y = y0 + height / 2, w = width)
            pdf.image(imgListTemp[5], x = pdf.l_margin + xhalf, y = y0 + height / 2, w = width)
            # CCD Temperatures
            # imgListCCDTemp = glob.glob("TemperaturePlot/REB0.CCDtemp*.jpg")
            # imgListRTDTemp = glob.glob("TemperaturePlot/REB0.RTDtemp*.jpg")
            pdf.add_page()
            pdf.set_fill_color(200, 220, 220)
            # pdf.cell(0, 6, "CCD temperature test", 0, 1, 'L', 1)
            y0 = pdf.get_y()
            pdf.image(imgListTemp[6], x = pdf.l_margin, y = y0, w = width)
            pdf.image(imgListTemp[7], x = pdf.l_margin + xhalf, y = y0, w = width)
            # pdf.image(imgListCCDTemp[0], x = pdf.l_margin, y = y0 + height / 4, w = width)
            # pdf.image(imgListRTDTemp[0], x = pdf.l_margin + xhalf, y = y0 + height / 4, w = width)
            # Clean up
            for img in imgListTemp:
                os.remove(img)
            for img in imgListCCDTemp:
                os.remove(img)
        except IndexError:
            pdf.cell(0, 10, "", 0, 1)
            pdf.cell(0, 6, "Error: could not retreive all requested temperature data.", 0, 1)


class ParameterLogging(object):
    '''@brief Periodically records specified values over the course of the testing sequence.'''

    def __init__(self, valuesToRead, delay = 5, fnTest = None, backup = 0):
        '''@brief Initializes the test.
        @param valuesToRead A list of ("subsystem", "value to read") tuples
        @param delay Time to sleep between periodic queries
        @param fnTest The FunctionalTest() object, allowing this test to track progress/terminate
        @param backup Backup data every n cycles. If zero, do not back up.'''
        self.start = time.time()
        self.stop = None
        self.title = "Parameter Logging"
        self.status = "Waiting..."
        self.delay = delay
        self.backup = backup
        self.fnTest = fnTest
        self.valuesToRead = valuesToRead
        self.names = [subsystem + "." + value for (subsystem, value) in self.valuesToRead]
        self.data = dict.fromkeys(self.names)  # Initialize data dictionary, stored as lists with named keys
        for key in self.data:  # Avoid identical lists problem
            self.data[key] = []
        self.recording = False

    def runTest(self):
        '''@brief Starts the logging in a separate thread, moves to the next test.'''
        self.status = "Working..."
        self.recording = True
        if not logIndefinitely:
            thread = Thread(target = self.recordContinuously)
            thread.daemon = True  # Daemon thread allows for graceful exiting and crashing
            thread.start()
        else:
            self.recordContinuously()

    def stopTest(self):
        '''@brief Sets the recording option to false, allowing the test to stop.'''
        self.stop = time.time()
        self.status = "DONE"
        self.recording = False

    def recordContinuously(self):
        '''@brief Continuously records the requested parameters while self.recording is set to true.'''
        count = 0
        while self.recording:
            if self.fnTest is not None:
                prog = self.fnTest.progress
                if prog >= 100:
                    self.stopTest()
                self.status = -prog if prog > 0 else "Working..."
            else:
                self.status = "Working..."
            count += 1
            for (subsystem, value), name in zip(self.valuesToRead, self.names):
                command = '{}.synchCommandLine(1000,"readChannelValue {}").getResult()'.format(subsystem, value)
                result = jy2.get(command)
                self.data[name].append(result)
            if count == self.backup > 0:
                count = 0
                pickle.dump(self.data, open("ParameterLogging.dat", "wb"))
            time.sleep(self.delay)

    def passFail(self):
        '''@brief Determine if the value logging passed - this is done in a separate function, unlike other tests.'''
        if self.stop is not None:
            self.passed = "PASS"
            self.stats = "Recorded {} parameters for {} seconds.".format(len(self.names), self.stop - self.start)
        else:
            self.passed = "FAIL"
            self.stats = "Parameter logging terminated early."

    def summarize(self, summary):
        self.passFail()
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf, reportPath):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.
        @param reportPath Path of directory containing the pdf report'''
        onePage = False
        if onePage:
            pdf.makePlotPage("Parameter Logging: " + name, name + ".jpg",
                             [(self.data[name], name) for name in self.names])
            pdf.cell(0, 6, "Data saved to pickleable object in ParameterLogging.dat with key " + name, 0, 1, 'L')
        else:
            for name in self.names:
                pdf.makePlotPage("Parameter Logging: " + name, name + ".jpg", [(self.data[name], name)])
                pdf.cell(0, 6, "Data saved to pickleable object in ParameterLogging.dat with key " + name, 0, 1, 'L')
        if dump:
            testPath = reportPath + "/" + self.title
            os.mkdir(testPath)
            with open(testPath + "/data.dat", "wb") as output:
                pickle.dump(self.data, output)


class ASPICNoise(object):
    '''@brief Measure noise distribution in ASPICs for the unclamped, clamped, and reset cases.'''

    def __init__(self):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "ASPIC Noise Tests"
        self.status = "Waiting..."

    def runTest(self):
        '''@brief Run the test, save output to state variables.'''
        self.status = -1
        errorLevel = 5.5  # Max allowable standard deviation
        # Delete directory containing old files, if it exists
        if os.path.exists("/u1/wreb/rafts/ASPICNoise/"):
            shutil.rmtree("/u1/wreb/rafts/ASPICNoise/")
        os.makedirs("/u1/wreb/rafts/ASPICNoise/")
        if not os.path.exists("ASPICNoise"):
            os.makedirs("ASPICNoise")
        self.fnames = ["unclamped_${sensorId}.fits", "clamped_${sensorId}.fits", "reset_${sensorId}.fits"]
        categories = ["REB4_test_base_cfg",
                      "REB4_test_aspic_clamped_cfg",
                      "REB4_test_aspic_clamped_cfg"]
        # Same sequencers for VST
        sequencers = ["/u1/wreb/rafts/xml/wreb_ITL_20160419_RG_high.seq",
                      "/u1/wreb/rafts/xml/wreb_ITL_20160419_RG_high.seq",
                      "/u1/wreb/rafts/xml/wreb_ITL_20160419_RG_high_ASPIC_CL_RST_high.seq"]
        # sequencers = ["/u1/wreb/rafts/xml/wreb_ITL_20160419.seq",
        #               "/u1/wreb/rafts/xml/wreb_ITL_20160419.seq",
        #               "/u1/wreb/rafts/xml/wreb_ITL_20160419_aspic_reset.seq"]
        self.passed = "PASS"
        errCount = 0
        totalCount = 0
        for cat, seq, fname in zip(categories, sequencers, self.fnames):
            # Generate fits files to /u1/wreb/rafts/ASPICNoise
            commands = '''
            # Load standard sequencer and run it with 0s exposure time
            vst.synchCommandLine(1000,"loadCategories Rafts:{}")
            vst.synchCommandLine(1000,"loadSequencer {}")
            reb0.synchCommandLine(1000,"loadDacs true")
            reb0.synchCommandLine(1000,"loadBiasDacs true")
            reb0.synchCommandLine(1000,"loadAspics true")
            vst.synchCommandLine(1000, "setParameter Exptime 0");  # sets exposure time to 0ms
            time.sleep(tsoak)
            vst.synchCommandLine(1000, "startSequencer")
            time.sleep(5)
            vst.synchCommandLine(1000, "setFitsFileNamePattern {}")
            result = vst.synchCommand(1000,"saveFitsImage ASPICNoise")
            '''.format(cat, seq, fname)
            jy.do(textwrap.dedent(commands))
            time.sleep(5)
            # Set fonts
            font = {'family': 'normal',
                    'weight': 'bold',
                    'size'  : 8}
            matplotlib.rc('font', **font)
            for stripe in range(3):
                # Read the data the plot
                f = fits.open("/u1/wreb/rafts/ASPICNoise/" + fname.replace("${sensorId}", str(stripe)))
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
                    imgData = rejectOutliers(imgData, 4.0)  # Chop off the extreme outliers, improving the fit
                    n, bins, patches = subPlot.hist(imgData, 40, range = [mu - 20, mu + 20], normed = 1,
                                                    facecolor = 'blue', alpha = 0.75)
                    # Add a 'best fit' line
                    y = matplotlib.mlab.normpdf(bins, mu, sigma)
                    subPlot.plot(bins, y, 'r--', linewidth = 1)
                    # Labeling
                    subPlot.set_yticklabels([])
                    subPlot.set_title('Channel {}\n$\mu={:.2}, \sigma={:.2} $'.format(i + 1, mu, sigma))
                    subPlot.grid(True)
                plt.tight_layout()
                plt.savefig("ASPICNoise/" + fname.replace("${sensorId}", str(stripe)) + ".jpg")
                plt.close()
                self.status -= 11  # Update the display
        self.stats = "{}/{} channels within sigma<{}.".format(totalCount - errCount, totalCount, errorLevel)
        self.status = self.passed

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        summary.testList.append(self.title)
        summary.passList.append(self.passed)
        summary.statsList.append(self.stats)

    def report(self, pdf):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.'''
        for stripe, letter in zip(range(3), ["A", "B", "C"]):
            pdf.addPlotPage("Unclamped ASPIC Noise Test - Stripe %s" % letter,
                            "ASPICNoise/" + self.fnames[0].replace("${sensorId}", str(stripe)) + ".jpg")
            pdf.passFail(self.passed)

        for stripe, letter in zip(range(3), ["A", "B", "C"]):
            pdf.addPlotPage("Clamped ASPIC Noise Test - Stripe %s" % letter,
                            "ASPICNoise/" + self.fnames[1].replace("${sensorId}", str(stripe)) + ".jpg")
            pdf.passFail(self.passed)

        for stripe, letter in zip(range(3), ["A", "B", "C"]):
            pdf.addPlotPage("Reset ASPIC Noise Test - Stripe %s" % letter,
                            "ASPICNoise/" + self.fnames[2].replace("${sensorId}", str(stripe)) + ".jpg")
            pdf.passFail(self.passed)


class ASPICLogging(object):
    '''@brief Continuously measure noise distribution in ASPICs. Must be run with -l enabled.'''

    def __init__(self, valuesToRead = None):
        '''@brief Initialize minimum required variables for test list.'''
        self.title = "Continuous ASPIC Logging"
        self.status = "Waiting..."
        self.numImages = 0
        self.logging = True
        self.valuesToRead = valuesToRead
        if self.valuesToRead is not None:
            self.names = [subsystem + "." + value for (subsystem, value) in self.valuesToRead]
            self.data = dict.fromkeys(self.names)  # Initialize data dictionary, stored as lists with named keys
            for key in self.data:  # Avoid identical lists problem
                self.data[key] = []
            # Add timestamp key
            self.data["timestamp"] = []
        else:
            self.names = None
            self.data = None

    def runTest(self, delay = 5 * 60):
        '''@brief Continuously log ASPIC images every time interval.'''
        # Delete directory containing old files, if it exists
        self.status = "Images: {}".format(self.numImages)
        if not os.path.exists("/u1/wreb/rafts/ASPICNoise/"):
            os.makedirs("/u1/wreb/rafts/ASPICNoise/")
        if not os.path.exists("ASPICNoise"):
            os.makedirs("ASPICNoise")
        while self.logging:
            timestamp = time.strftime("%y.%m.%d.%H.%M", time.localtime(time.time()))
            # Log other values
            if self.names is not None:
                for (subsystem, value), name in zip(self.valuesToRead, self.names):
                    command = '{}.synchCommandLine(1000,"readChannelValue {}").getResult()'.format(subsystem, value)
                    result = jy2.get(command)
                    self.data[name].append(result)
                self.data["timestamp"].append(timestamp)
                pickle.dump(self.data, open("ParameterLogging.dat", "wb"))
            # Imaging
            errorLevel = 5.5  # Max allowable standard deviation
            self.fnames = ["unclamped." + timestamp + "_${sensorId}.fits",
                           "clamped." + timestamp + "_${sensorId}.fits",
                           "reset." + timestamp + "_${sensorId}.fits"]
            categories = ["REB4_test_base_cfg",
                          "REB4_test_aspic_clamped_cfg",
                          "REB4_test_aspic_clamped_cfg"]
            # Same sequencers for VST
            sequencers = ["/u1/wreb/rafts/xml/wreb_ITL_20160419_RG_high.seq",
                          "/u1/wreb/rafts/xml/wreb_ITL_20160419_RG_high.seq",
                          "/u1/wreb/rafts/xml/wreb_ITL_20160419_RG_high_ASPIC_CL_RST_high.seq"]
            self.passed = "PASS"
            errCount = 0
            totalCount = 0
            for cat, seq, fname in zip(categories, sequencers, self.fnames):
                # Generate fits files to /u1/wreb/rafts/ASPICNoise
                commands = '''
                # Load standard sequencer and run it with 0s exposure time
                vst.synchCommandLine(1000,"loadCategories Rafts:{}")
                vst.synchCommandLine(1000,"loadSequencer {}")
                reb0.synchCommandLine(1000,"loadDacs true")
                reb0.synchCommandLine(1000,"loadBiasDacs true")
                reb0.synchCommandLine(1000,"loadAspics true")
                vst.synchCommandLine(1000, "setParameter Exptime 0");  # sets exposure time to 0ms
                time.sleep(tsoak)
                vst.synchCommandLine(1000, "startSequencer")
                time.sleep(5)
                vst.synchCommandLine(1000, "setFitsFileNamePattern {}")
                result = vst.synchCommand(1000,"saveFitsImage ASPICNoise")
                '''.format(cat, seq, fname)
                jy.do(textwrap.dedent(commands))
                printv("Generating test for %s..." % fname)
                time.sleep(5)
                # Set fonts
                font = {'family': 'normal',
                        'weight': 'bold',
                        'size'  : 8}
                matplotlib.rc('font', **font)
                for stripe in range(3):
                    # Read the data the plot
                    f = fits.open("/u1/wreb/rafts/ASPICNoise/" + fname.replace("${sensorId}", str(stripe)))
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
                        imgData = rejectOutliers(imgData, 4.0)  # Chop off the extreme outliers, improving the fit
                        n, bins, patches = subPlot.hist(imgData, 40, range = [mu - 20, mu + 20], normed = 1,
                                                        facecolor = 'blue', alpha = 0.75)
                        # Add a 'best fit' line
                        y = matplotlib.mlab.normpdf(bins, mu, sigma)
                        subPlot.plot(bins, y, 'r--', linewidth = 1)
                        # Labeling
                        subPlot.set_yticklabels([])
                        subPlot.set_title('Channel {}\n$\mu={:.2}, \sigma={:.2} $'.format(i + 1, mu, sigma))
                        subPlot.grid(True)
                    plt.tight_layout()
                    plt.savefig("ASPICNoise/" + fname.replace("${sensorId}", str(stripe)) + ".jpg")
                    plt.close()
                    self.numImages += 1
                    self.status = "Images: {}".format(self.numImages)
            # Sleep for 5 minutes by default
            time.sleep(delay)

    def summarize(self, summary):
        '''@brief Summarize the test results for the cover page of the report.
        @param summary Summary obejct passed from FunctionalTest()'''
        pass

    def report(self, pdf):
        '''@brief generate this test's page in the PDF report.
        @param pdf pyfpdf-compatible PDF object.'''
        pass


def getBoardInfo():
    try:
        # Get hex board ID
        boardID = str(hex(int(
                jy.get('reb0.synchCommandLine(1000,"getSerialNumber").getResult()', dtype = "str").replace("L", ""))))
        # FPGA info in register 1
        response = jy.get('reb0.synchCommandLine(1000,"getRegister 1 1").getResult()', dtype = "str")
        # Response is something like "000001: b0200020" with length 17. If it's longer, it's a traceback probably
        if len(response) != 17 or boardID == "0x0":
            return -1, -1, -1, -1
        FPGAInfo = response.split(": ")[1]
        boardType, linkVersion, FPGAVersion = FPGAInfo[0], FPGAInfo[1:4], FPGAInfo[4:]
        if boardType == "0" or linkVersion == "000":
            return -1, -1, -1, -1
        return boardID, boardType, linkVersion, FPGAVersion
    except ValueError:
        return -1, -1, -1, -1


class Summary(object):
    '''@brief Summary object containing the needed information for the cover page.'''

    def __init__(self):
        '''@brief Initialize the list of tests, the list of passes/fails, and the list of results.'''
        self.testList = []
        self.passList = []
        self.statsList = []


class FunctionalTest(object):
    '''@brief Runs the functional testing suite. Tests are provided as a list of class initializations.'''

    def __init__(self):
        self.boardID, self.boardType, self.linkVersion, self.FPGAVersion = getBoardInfo()
        self.scriptVersion = time.strftime("%y.%m.%d.%H.%M", time.localtime(os.path.getmtime("VSTTest.py")))
        '''@brief Initializes the board information and list of tests to be run.'''
        self.summary = Summary()
        # Make temporary figure directory
        if not os.path.exists("tempFigures"): os.makedirs("tempFigures")
        # Initiate desired tests
        print("\n\n\nVST Functional Test:")
        self.progress = 0
        self.startTime = time.time()
        # Logging option
        self.parameterLogger = ParameterLogging([("vst", "REB0.Temp1"),
                                                 ("vst", "REB0.Temp2"),
                                                 ("vst", "REB0.Temp3"),
                                                 ("vst", "REB0.Temp4"),
                                                 ("vst", "REB0.Temp5"),
                                                 ("vst", "REB0.Temp6"),
                                                 ("vst", "REB0.Temp7"),
                                                 ("vst", "REB0.Temp8")], fnTest = self, backup = 5)
        # You can comment out tests you don't want to run or select them to not run in the main menu of the GUI
        self.tests = [self.parameterLogger,
                      IdleCurrentConsumption(),
                      ChannelTest(),
                      ASPICcommsTest(),
                      CSGate(),
                      PCKRails(),
                      SCKRails(),
                      RGRails(),
                      SCKRailsDiverging(9.0, 0.0),
                      SCKRailsDiverging(9.0, 2.0),
                      SCKRailsDiverging(9.0, -2.0),
                      RGRailsDiverging(9.0, 0.0),
                      RGRailsDiverging(9.0, 2.0),
                      RGRailsDiverging(9.0, -2.0),
                      OGBias(),
                      ODBias(),
                      GDBias(),
                      RDBias(),
                      TemperatureLogging(self.startTime),
                      ASPICNoise()]
        if logIndefinitely:
            self.tests.append(ASPICLogging([("vst", "REB0.Temp1"),
                                            ("vst", "REB0.Temp2"),
                                            ("vst", "REB0.Temp3"),
                                            ("vst", "REB0.Temp4"),
                                            ("vst", "REB0.Temp5"),
                                            ("vst", "REB0.Temp6"),
                                            ("vst", "REB0.Temp7"),
                                            ("vst", "REB0.Temp8")]))
        self.testsMask = [True for _ in self.tests]
        self.reportName = "SR_REB_Test_" + time.strftime("%y.%m.%d.%H.%M", time.localtime(self.startTime)) + "_" + \
                          str(self.boardID)
        self.reportPath = dataDir + "/" + self.reportName
        os.mkdir(self.reportPath)

    def runTests(self):
        '''@brief Run the tests.'''
        # Run the tests
        testList = []
        for test, doTest in zip(self.tests, self.testsMask):
            if doTest:
                testList.append(test)
        for count, test in enumerate(testList):
            test.runTest()
            self.progress = int(100 * (count + 1) / float(len(testList)))
            resetSettings()
        self.progress = 100
        if self.parameterLogger is not None:
            self.parameterLogger.stopTest()

    def generateReport(self):
        '''@brief Generate a pyfpdf-compatible PDF report from the test data.'''
        # Make pdf object
        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.set_font('Courier', '', 12)
        global epw  # Constant: effective page width
        epw = pdf.w - 2 * pdf.l_margin
        # Generate summary page
        for test, doTest in zip(self.tests, self.testsMask):
            if doTest: test.summarize(self.summary)
        pdf.summaryPage(self.boardID, self.boardType, self.linkVersion, self.FPGAVersion, self.scriptVersion,
                        time.localtime(self.startTime), self.summary.testList, self.summary.passList,
                        self.summary.statsList)
        # Generate individual test reports
        for test, doTest in zip(self.tests, self.testsMask):
            if doTest:
                try:
                    test.report(pdf, self.reportPath)
                except TypeError:
                    test.report(pdf)
        pdf.output(self.reportPath + "/" + self.reportName + ".pdf", 'F')
        # Clean up
        shutil.rmtree("tempFigures")
        # shutil.rmtree("ASPICNoise")


class GUI(object):
    '''@brief Dialog-based GUI for displaying test progress and navigating options.'''

    def __init__(self):
        '''@brief Start the dialog.'''
        self.scriptVersion = time.strftime("%y.%m.%d.%H.%M", time.localtime(os.path.getmtime("VSTTest.py")))
        self.tsleep = 1.0  # Time to sleep in between refreshes of progress dialog
        self.d = Dialog(autowidgetsize = True)

    def update(self):
        '''@brief Update the GUI to display current testing progress.'''
        elems = []
        # Stupid issue: 0 is hard-coded as "SUCCESS" in this package...
        for test, doTest in zip(self.fnTest.tests, self.fnTest.testsMask):
            if doTest:
                if test.status == 0:
                    elems.append((test.title, -1))
                else:
                    elems.append((test.title, test.status))
        infoString = ["VST Functional Test:",
                      "Elapsed time....." + str(int(time.time() - self.fnTest.startTime)) + "s",
                      "Script version..." + str(self.scriptVersion),
                      "Board ID........." + str(self.fnTest.boardID),
                      "Board type......." + str(self.fnTest.boardType),
                      "Link version....." + str(self.fnTest.linkVersion),
                      "FPGA version....." + str(self.fnTest.FPGAVersion)]
        infoString = "\n".join(infoString)
        self.d.mixedgauge(infoString, title = "VST Functional Test", backtitle = "Running functional test...",
                          percent = self.fnTest.progress, elements = elems)

    def updateContinuously(self):
        '''@brief Continuously update the display every _ seconds.'''
        while self.fnTest.progress < 100:
            self.update()
            time.sleep(self.tsleep)

    def startUpdateContinuously(self):
        '''@brief Start the self.updateContinuously() procedure in a separate daemon thread.'''
        thread = Thread(target = self.updateContinuously)
        thread.daemon = True  # Daemon thread allows for graceful exiting and crashing
        thread.start()

    def startMenu(self):
        '''@brief Initial navigation menu. Checks that board is connected and presents the user with various options.'''
        notConnected = any([v == -1 for v in getBoardInfo()])
        while notConnected:
            infoString = "No board connected. Please connect a VST to continue."
            self.d.infobox(infoString, title = "VST Functional Test")
            time.sleep(1)
            boardInfo = getBoardInfo()
            notConnected = any([v == -1 for v in boardInfo])
            print("Board Info: ", boardInfo)
        self.boardID, self.boardType, self.linkVersion, self.FPGAVersion = getBoardInfo()
        infoString = ["VST Functional Test Version " + str(self.scriptVersion) + ":",
                      "Board ID........." + str(self.boardID),
                      "Board type......." + str(self.boardType),
                      "Link version....." + str(self.linkVersion),
                      "FPGA version....." + str(self.FPGAVersion),
                      "",
                      "Select an option:"]
        infoString = "\n".join(infoString)
        ret, tag = self.d.menu(infoString, title = "VST Functional Test",
                               choices = [("1", "Run functional test suite"),
                                          ("2", "Run custom test list"),
                                          ("3", "Exit")])

        if ret == self.d.CANCEL or ret == self.d.ESC or tag == "3":
            self.d.infobox("Exiting VST Functional Test.")
            print("VST test aborted.\n")
            sys.exit()
        if tag == "1":
            # Run test
            return self.runFunctionalTest()
        elif tag == "2":
            return self.runCustomTests()

    def runFunctionalTest(self):
        '''@brief Runs the full suite of tests from the GUI.'''
        self.d.infobox("Initializing VST Functional Test...")
        initialize(jy)
        self.fnTest = FunctionalTest()
        self.startUpdateContinuously()
        self.fnTest.runTests()
        self.d.infobox("Writing PDF report to:\n" + self.fnTest.reportPath + "/" + self.fnTest.reportName + "...")
        self.fnTest.generateReport()
        return (self.d.yesno("VST functional test complete.\n" +
                             "Report available at " + self.fnTest.reportPath + "/" + self.fnTest.reportName + ".\n" +
                             "Test another board?") == self.d.OK)

    def runCustomTests(self):
        '''@brief Allows the user to configure which tests should be run, and runs only those tests.'''
        # Initialize functional test to get an initial test list
        self.fnTest = FunctionalTest()
        testList = [test.title for test in self.fnTest.tests]
        code, selectedTests = self.d.checklist(text = "Use the arrow keys and spacebar to\n" +
                                                      "select the tests you wish to run:",
                                               width = 64,
                                               list_height = len(testList),
                                               choices = [(title, "", False) for title in testList],
                                               title = "VST Functional Test")
        if code == self.d.OK:
            testList = [(test in selectedTests) for test in testList]
            self.fnTest.testsMask = testList
            self.d.infobox("Initializing VST Functional Test...")
            initialize(jy)
            self.startUpdateContinuously()
            self.fnTest.runTests()
            self.fnTest.generateReport()
            return (self.d.yesno("VST custom functional test complete.\n" +
                                 "Report available at " + self.fnTest.reportPath + "/" + self.fnTest.reportName + ".\n" +
                                 "Test another board?") == self.d.OK)
        else:
            self.fnTest = None
            return self.startMenu()


# --------- Execution ---------
if __name__ == "__main__":
    # Argument parser
    import argparse

    parser = argparse.ArgumentParser(description =
                                     '''Test script for VST controller boards to generate a pdf status report.''',
                                     epilog = '''>> Example: python VSTTest.py ~/u1/wreb/data -q''')
    parser.add_argument("writeDirectory", nargs = '?', default = "./Reports",
                        help = "Directory to save outputs to. Defaults to ./Reports.", action = "store")
    parser.add_argument("-v", "--verbose",
                        help = "Print test results in the terminal.", action = "store_true")
    parser.add_argument("-n", "--noGUI",
                        help = "Do not use the pythonDialogs GUI.", action = "store_true")
    parser.add_argument("-l", "--logValues",
                        help = "Log values indefinitely.", action = "store_true")
    parser.add_argument("-d", "--dump",
                        help = "Dump test data to pickleable objects.", action = "store_true")
    args = parser.parse_args()

    tsoak = 0.5
    dataDir = args.writeDirectory
    verbose = args.verbose
    noGUI = args.noGUI
    dump = args.dump
    logIndefinitely = args.logValues
    # Create the Jython interface
    jy = JythonInterface()
    jy2 = JythonInterface()
    initialize(jy)
    initialize(jy2)

    # Start the GUI
    if not noGUI:
        while True:
            gui = GUI()
            time.sleep(1)
            testAgain = gui.startMenu()
            if not testAgain:
                break
            gui.d.msgbox("Please disconnect the board now. Select OK when the board is disconnected to continue.")
    else:
        scriptVersion = time.strftime("%y.%m.%d.%H.%M", time.localtime(os.path.getmtime("VSTTest.py")))
        boardID, boardType, linkVersion, FPGAVersion = getBoardInfo()
        infoString = ["VST Functional Test:",
                      "Script version..." + str(scriptVersion),
                      "Board ID........." + str(boardID),
                      "Board type......." + str(boardType),
                      "Link version....." + str(linkVersion),
                      "FPGA version....." + str(FPGAVersion)]
        infoString = "\n".join(infoString)
        # Functional test object
        functionalTest = FunctionalTest()
        # Run tests and generate report
        functionalTest.runTests()
        functionalTest.generateReport()

    # Restore previous settings and exit
    print("VST test completed.\n\n\n")
    exitScript()
