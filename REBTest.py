'''
@file WREBTest.py
@brief Suite of tests for the WREB controller board.
This program communicates directly with the Jython interpreter to
manipulate the board, so it does not need to be loaded into the Jython exectuor.

External dependencies:
- astropy
- numpy
- matplotlib
- Unix Dialogs installation (for GUI, optional)

To run:
- Ensure Jython console is running (./JythonConsole or the bootstrapper program)
- Ensure crRun.sh is running
- "python WREBTest.py [options]"
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
import pickle
import signal
import textwrap
import numpy as np
import matplotlib

matplotlib.use('Agg')  # Fixes "RuntimeError: Invalid DISPLAY variable" error
import matplotlib.pyplot as plt
from astropy.io import fits
from pdfGenWREB import *
from threading import Thread
from datetime import datetime

from Libraries.FastProgressBar import progressbar
from Libraries.PythonBinding import *
from Libraries.dialog import Dialog


def exitScript():
    '''@brief Reset settings and exit. Usually catches ^C.'''
    resetSettings()
    print("\nTests concluded or ^C raised. Restoring saved temp config and exiting...")
    sys.exit()


signal.signal(signal.SIGINT, exitScript)

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


def getBoardInfo():
    try:
        # Get hex board ID
        boardID = str(hex(int(
                jy.get('wreb.synchCommandLine(1000,"getSerialNumber").getResult()', dtype = "str").replace("L", ""))))
        # FPGA info in register 1
        response = jy.get('wreb.synchCommandLine(1000,"getRegister 1 1").getResult()', dtype = "str")
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


class GUI(object):
    '''@brief Dialog-based GUI for displaying test progress and navigating options.'''

    def __init__(self):
        '''@brief Start the dialog.'''
        self.scriptVersion = time.strftime("%y.%m.%d.%H.%M", time.localtime(os.path.getmtime("WREBTest.py")))
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
        infoString = ["WREB Functional Test:",
                      "Elapsed time....." + str(int(time.time() - self.fnTest.startTime)) + "s",
                      "Script version..." + str(self.scriptVersion),
                      "Board ID........." + str(self.fnTest.boardID),
                      "Board type......." + str(self.fnTest.boardType),
                      "Link version....." + str(self.fnTest.linkVersion),
                      "FPGA version....." + str(self.fnTest.FPGAVersion)]
        infoString = "\n".join(infoString)
        self.d.mixedgauge(infoString, title = "WREB Functional Test", backtitle = "Running functional test...",
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
            infoString = "No board connected. Please connect a WREB to continue."
            self.d.infobox(infoString, title = "WREB Functional Test")
            time.sleep(1)
            boardInfo = getBoardInfo()
            notConnected = any([v == -1 for v in boardInfo])
            print("Board Info: ", boardInfo)
        self.boardID, self.boardType, self.linkVersion, self.FPGAVersion = getBoardInfo()
        infoString = ["WREB Functional Test Version " + str(self.scriptVersion) + ":",
                      "Board ID........." + str(self.boardID),
                      "Board type......." + str(self.boardType),
                      "Link version....." + str(self.linkVersion),
                      "FPGA version....." + str(self.FPGAVersion),
                      "",
                      "Select an option:"]
        infoString = "\n".join(infoString)
        ret, tag = self.d.menu(infoString, title = "WREB Functional Test",
                               choices = [("1", "Run functional test suite"),
                                          ("2", "Run custom test list"),
                                          ("3", "Exit")])

        if ret == self.d.CANCEL or ret == self.d.ESC or tag == "3":
            self.d.infobox("Exiting WREB Functional Test.")
            print("WREB test aborted.\n")
            sys.exit()
        if tag == "1":
            # Run test
            return self.runFunctionalTest()
        elif tag == "2":
            return self.runCustomTests()

    def runFunctionalTest(self):
        '''@brief Runs the full suite of tests from the GUI.'''
        self.d.infobox("Initializing WREB Functional Test...")
        initialize(jy)
        self.fnTest = FunctionalTest()
        self.startUpdateContinuously()
        self.fnTest.runTests()
        self.d.infobox("Writing PDF report to:\n" + dataDir + "/" + self.fnTest.reportName + "...")
        self.fnTest.generateReport()
        return (self.d.yesno("WREB functional test complete.\n" +
                             "Report available at " + dataDir + "/" + self.fnTest.reportName + ".\n" +
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
                                               title = "WREB Functional Test")
        if code == self.d.OK:
            testList = [(test in selectedTests) for test in testList]
            self.fnTest.testsMask = testList
            self.d.infobox("Initializing WREB Functional Test...")
            initialize(jy)
            self.startUpdateContinuously()
            self.fnTest.runTests()
            self.fnTest.generateReport()
            return (self.d.yesno("WREB custom functional test complete.\n" +
                                 "Report available at " + dataDir + "/" + self.fnTest.reportName + ".\n" +
                                 "Test another board?") == self.d.OK)
        else:
            self.fnTest = None
            return self.startMenu()


# --------- Execution ---------
if __name__ == "__main__":
    # Argument parser
    import argparse

    parser = argparse.ArgumentParser(description =
                                     '''Test script for WREB controller boards to generate a pdf status report.''',
                                     epilog = '''>> Example: python WREBTest.py ~/u1/wreb/data -q''')
    parser.add_argument("writeDirectory", nargs = '?', default = "./Reports",
                        help = "Directory to save outputs to. Defaults to ./Reports.", action = "store")
    parser.add_argument("-v", "--verbose",
                        help = "Print test results in the terminal.", action = "store_true")
    parser.add_argument("-n", "--noGUI",
                        help = "Do not use the pythonDialogs GUI.", action = "store_true")
    parser.add_argument("-l", "--logValues",
                        help = "Log values indefinitely.", action = "store_true")
    args = parser.parse_args()

    tsoak = 0.5
    dataDir = args.writeDirectory
    verbose = args.verbose
    noGUI = args.noGUI
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
        scriptVersion = time.strftime("%y.%m.%d.%H.%M", time.localtime(os.path.getmtime("WREBTest.py")))
        boardID, boardType, linkVersion, FPGAVersion = getBoardInfo()
        infoString = ["WREB Functional Test:",
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
    print("WREB test completed.\n\n\n")
    exitScript()
