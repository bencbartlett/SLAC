# WREB Testing Suite

This is the testing suite for the WREB CCD interface, designed to verify that the WREB boards are defect-free and operating as expected. Note that this program communicates directly with the Jython interpreter to manipulate the board, so it does not need to be loaded into the Jython exectuor and can be run directly from the terminal with python.

Tests are structured as classes with four required methods:
- __init__ sets initial variables; minimum required variables are self.title and self.status.
- runTest is the body of the tests, running the code to execute the tests and storing the results to state variables.
- summarize writes summary information to the summary object passed to it; this is used in generating the cover page.
- report writes the portion of the pdf report that the test is responsible for.


## External dependencies 
All external dependencies are contained within Anaconda:
- astropy 
- numpy
- matplotlib

## Running the testing suite
- Ensure Jython console is running (./JythonConsole or the bootstrapper program)
- Ensure crRun.sh is running
- Ensure DACs are loaded in the CCS console
- "python WREBTest.py [options]"
Initial crashing yielding a ValueError is likely due to a crRun or JythonConsole crashing or not being loaded.
