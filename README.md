# LSST Readout Electronics Boards Testing Suite

## [Documentation](https://bencbartlett.github.io/SLAC/)

## Introduction
This is the testing suite for the readout electronics boards for the LSST CCD interface, designed to verify that the boards are defect-free and operating as expected. Note that this program communicates directly with the Jython interpreter to manipulate the board, so it does not need to be loaded into the Jython exectuor and can be run directly from the terminal with python.


### Test versions
There are three separate versions of this test to cover the three types of readout boards:
1. WREBTest.py: for the single-stripe corner raft board (WREB)
2. GREBTest.py: for the double-stripe guider board (GREB)
3. VSTTest.py: for the triple-stripe science raft board (VST)

Presently, the WREB test is fully functional and a board (SN:03) passes all applicable tests. The VST test is also fully functional, though there are some minor gain errors possibly due to invalid resistor values that prevent boards we have tested from being able to pass all tests. The GREBTest is not fully functional, as the CCS system for it was still being developed at the conclusion of my time working on this project, though I have mostly adapted the code to work once the CCS is fully implemented for it.

## External dependencies 
All external dependencies are contained within Anaconda:
- astropy 
- numpy
- matplotlib

Additionally, the program requires a UNIX dialogs-like executable for the GUI to be run (default), which is installed by default on most Linux systems, including RHEL6.

## Running the testing suite
- Ensure Jython console is running (./JythonConsole or the bootstrapper program)
- Ensure `rebRun.sh` is running
- `python REBTest.py [options]`
Initial crashing yielding a ValueError is likely due to a `rebRun.sh` or `JythonConsole` crashing or not being loaded.

## Subtests

### Test structure
Individual tests are structured as classes with four required methods:
- `__init__` sets initial variables; minimum required variables are `self.title` and `self.status`.
- `runTest` is the body of the tests, running the code to execute the tests and storing the results to state variables.
- `summarize` writes summary information to the summary object passed to it; this is used in generating the cover page.
- `report` writes the portion of the pdf report that the test is responsible for and dumps the raw data into the report directory structure if `-d` is called with the program.

### List of subtests
- `IdleCurrentConsumption`: reads the idle current consumption across parts of the readout board. Pass metric: none
- `ChannelTest`: obtains the list of comminicable channels. Pass metric: passes if number of channels is the expected value (must be updated, is not current in GREB or VST tests)
- `ASPICcommsTest`: tests that the readout board can communicate with the ASPICS. Pass metric: passes if `<subsystem> checkAspics` returns a list of zeros, indicating the ability to read and write from the ASPIC-associated registers
- `SequencerToggling` (WREB test only): toggles the sequencer outputs for the parallel clock, serial clock, and reset gate rails. Pass metric: none
- `CSGate` (implemented on all tests, but only functional on WREB test): Tests the performance of the current source gate. Pass metric: not implemented
- `PCKRails`: Scales the parallel clock rails over a range of voltages with a constant rail potential difference. Pass metric: upper and lower gain within ROI are close to 1 and fewer than N points are further than X from the expected value.
- `SCKRails`: Scales the serial clock rails over a range of voltages with a constant rail potential difference. Pass metric: upper and lower gain within ROI are close to 1 and fewer than N points are further than X from the expected value.
- `SCKRailsDiverging`: Scales the serial clock rails over a range of voltages with an increasing rail potential difference. Pass metric: upper and lower gain within ROI are close to 1 and fewer than N points are further than X from the expected value.
- `RGRails`: Scales the reset gate rails over a range of voltages with a constant rail potential difference. Pass metric: upper and lower gain within ROI are close to 1 and fewer than N points are further than X from the expected value.
- `RGRailsDiverging`: Scales the reset gate clock rails over a range of voltages with an increasing rail potential difference. Pass metric: upper and lower gain within ROI are close to 1 and fewer than N points are further than X from the expected value.
- `OGBias`: Tests the output gate performance by scaling it over a range of potentials and testing for linearity. Pass metric: fewer than N points are further than X from the expected value.
- `ODBias`: Tests the output drain performance by scaling it over a range of potentials and testing for linearity. Pass metric: fewer than N points are further than X from the expected value.
- `GDBias`: Tests the guard drain performance by scaling it over a range of potentials and testing for linearity. Pass metric: fewer than N points are further than X from the expected value.
- `RDBias`: Tests the reset drain performance by scaling it over a range of potentials and testing for linearity. Pass metric: fewer than N points are further than X from the expected value.
- `TemperatureLogging`: Queries the board's internal trending database to obtain the temperature values while the test has been running. Largely depricated due to poor functionality in the database retrieval program. An alternative is `ParameterLogging`, which actively queries the board for the desired properties during the course of the test. Pass metric: none
- `ParameterLogging`: Actively queries the board in a separate thread for the desired properties while the test is running. Using `-l` or `--logValues` while calling the program will allow you to actively log these values without a time limit. Pass metric: none
- `ASPICNoise`: Obtains a fits image from each ASPIC in the readout board. Analyses the images to measure the noise distribution and mean pixel value across the image. This test is run with three different sequencers: unclamped, clamped, and reset. Pass metric: no channels have a standard deviation in pixel value larger than X (currently 5.5).
- `ASPICLogging`: Continually runs the ASPICNoise tests periodically; this was used for thermocycling testing over long periods of time. This test must be run with `-l` enabled.

## Contact
My SLAC email (`bcb@slac.stanford.edu`) will be terminated when I leave SLAC in September. If something is wrong, confusing, or not working, feel free to contact me after I have left SLAC at `bartlett@caltech.edu`.
