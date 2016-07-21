'''
@file pdfGenWREB.py
@brief Contains common PDF generation routines for the WREB test report.

External dependencies:
- Matplotlib
- Numpy
'''

# PDF Report Generator for WREBTest.py
# Ben Bartlett
# 15 June 2016

import time

import matplotlib.pyplot as plt
import numpy as np

from Libraries.fpdf.fpdf import FPDF


def residualPlots(datas, residuals, saveAs, ROI = None, xdat = None, pltRange = None):
    '''@brief Generates a set of plots and residuals.
    @param datas Zipped data arrays and legend titles
    @param residuals Zipped array of residuals and legend titles
    @param saveAs Filename to save plot as
    @param ROI Optional parameter specifying region of interest in the plot
    @param xdat Optional zipped array of x values and titles. Defaults to iteration values.
    @param pltRange Optional specified plot range.
    '''
    if xdat is None:
        xvals = range(len(datas[0][0]))
        xlabel = "Iteration"
    else:
        xvals, xlabel = xdat
    fig1 = plt.figure(1)
    frame1 = fig1.add_axes((.1, .3, .8, .6))
    for data, legtitle in datas:
        plt.plot(xvals, data, label = legtitle)
    # legendtitles = [legtitle for data, legtitle in datas]
    if pltRange is not None:
        plt.ylim(pltRange)
    plt.legend(loc = 'upper left', prop = {'size': 8})
    frame1.set_xticklabels([])  # Remove x-tic labels for the first frame
    plt.grid()
    # ROI
    if ROI is not None:
        plt.axvspan(ROI[0], ROI[1], facecolor = '0.5', alpha = 0.5)
        plt.text(np.mean(ROI), frame1.get_ylim()[1] * .9, "ROI")
    # Residual plot
    frame2 = fig1.add_axes((.1, .1, .8, .2))
    for data, legtitle in residuals:
        plt.plot(xvals, data, 'o', label = legtitle)
    # legendtitles = [legtitle for data, legtitle in residuals]
    plt.legend(loc = 'upper left', prop = {'size': 8})
    plt.xlabel(xlabel)
    plt.grid()
    # ROI for second subplot
    if ROI is not None:
        plt.axvspan(ROI[0], ROI[1], facecolor = '0.5', alpha = 0.5)
        # plt.text(np.mean(ROI), frame1.get_ylim()[1]*.9, "ROI")
    # Render to image
    fig1.savefig(saveAs)
    plt.close()


def multiPlots(datas, saveAs, xdat = None):
    '''@brief Generates a set of plots.
    @param datas Zipped data arrays and legend titles
    @param saveAs Filename to save plot as
    @param xdat Optional zipped array of x values and titles. Defaults to iteration values.
    '''
    if xdat is None:
        xvals = range(len(datas[0][0]))
        xlabel = "Iteration"
    else:
        xvals, xlabel = xdat
    fig1 = plt.figure(1)
    for data, legtitle in datas:
        plt.plot(xvals, data)
    legendtitles = [legtitle for data, legtitle in datas]
    plt.legend(legendtitles, loc = 'upper left')
    plt.xlabel(xlabel)
    plt.grid()
    # Render to image
    fig1.savefig(saveAs)
    plt.close()


class PDF(FPDF):
    '''@brief PDF generation class for reports'''

    def header(self):
        '''@brief Adds a LSST/SLAC header and title to every page.'''
        # Logo
        self.image('Media/LSSTLogo.jpg', 10, 8, h = 15)  # For some reason, fpdf doesn't like png's, only jpgs.
        # Courier bold 15
        self.set_font('Courier', 'B', 15)
        # Move to the right
        self.cell(80)
        # Title
        self.cell(30, 10, 'WREB Test: ' + time.strftime("%Y-%m-%d %H:%M"), align = 'C')
        self.image('Media/SLACLogo.jpg', 150, 8, h = 15)
        # Line break
        self.ln(20)

    def footer(self):
        '''@brief Adds page numbers to every page.'''
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Courier italic 8
        self.set_font('Courier', 'I', 8)
        # Page number
        self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    def testTitle(self, title):
        '''@brief Generic title function for tests.'''
        # Courier 12
        self.set_font('Courier', '', 12)
        # Background color
        self.set_fill_color(200, 220, 220)
        # Title
        self.cell(0, 6, title, 0, 1, 'L', 1)
        # Line break
        self.ln(4)

    def summaryPage(self, boardID, boardType, linkVersion, FPGAVersion, scriptVersion, startTime, testList, passList, statsList):
        '''@brief Generate a summary page for the tests that were run.
        @param boardID Serial number of the board that is tested
        @param boardType Type of phsyical board model
        @param linkVersion Version of link software
        @param FPGAVersion Front-end FPGA code version
        @param scriptVersion Version of the script, given by the last modified date YY.MM.DD.hh.mm.ss
        @param testList List of test titles that were run
        @param passList List of test results
        @param statsList List of relevant statistics returned from the tests'''
        self.add_page()
        # Logo
        self.image('Media/LSSTLogo.jpg', 10, 8, h = 15)  # For some reason, fpdf doesn't like png's, only jpgs.
        # Move to the right
        self.cell(110)
        self.image('Media/SLACLogo.jpg', 150, 8, h = 15)
        # Title
        self.set_font('Courier', 'B', 18)
        self.ln(4 * self.font_size)
        epw = self.w - 2 * self.l_margin
        # Board info
        self.cell(epw, self.font_size, 'WREB Functional Test Report', align = 'C', ln = 1)
        self.ln(2 * self.font_size)
        self.set_font('Courier', size = 14)
        self.cell(epw, self.font_size, 'Board ID......................' + boardID, align = 'L', ln = 1)
        self.cell(epw, self.font_size, 'Board Type....................' + boardType, align = 'L', ln = 1)
        self.cell(epw, self.font_size, 'Link Version..................' + linkVersion, align = 'L', ln = 1)
        self.cell(epw, self.font_size, 'Front-end FPGA Code Version...' + FPGAVersion, align = 'L', ln = 1)
        self.cell(epw, self.font_size, 'Script Version................' + scriptVersion, align = 'L', ln = 1)
        self.cell(epw, self.font_size, 'Test Performed................' + time.strftime("%Y-%m-%d %H:%M:%S", startTime),
                  align = 'L', ln = 1)
        self.ln(2 * self.font_size)
        # Summary table
        self.columnTable([passList, testList, statsList], colHeaders = ["Status", "Test", "Results"],
                         fontSize = 9, widthArray = [0.3, 0.8, 2.0])

    def columnTable(self, colData, ROI = None, colHeaders = None, fontSize = 8, width = 1.0, widthArray = None,
                    align = "L"):
        '''@brief Generates a table from a list of lists of column data.
        @param colData Tuple of column information as ([data], header) to be put in a column, from left to right.
        @param ROI Optional parameter of [low, high] index of cells to be highlighted as a region of interest.
        @param colHeaders Optional list of headers for columns; if specified, colData is expected as ([data],[data],...)
        @param fontSize Optional font size for the table.
        @param width Percent of page width the table should occupy.
        @param widthArray Non-normalized list of relative column widths. Defaults to every column having equal width.
        @param align Align as left ("L"), center ("C"), right ("R")'''
        originalFontSize = self.font_size
        self.set_font_size(fontSize)  # Small font
        epw = self.w - 2 * self.l_margin
        cellHeight = self.font_size  # Height of cell is equal to font size
        tableStartX = self.get_x()
        tableStartY = self.get_y()
        if ROI is not None:
            low, high = ROI
        else:
            low = -1
            high = -1
        if widthArray is None:
            colWidths = width * epw * np.ones(len(colData)) / len(colData)
        else:
            colWidths = width * epw * np.array(widthArray) / np.sum(widthArray)
        for column, colWidth in zip(colData, colWidths):
            # Reset the position
            self.set_y(tableStartY)
            self.set_x(tableStartX)
            tableStartX += colWidth

            if colHeaders is None:
                data, title = column
            else:
                data = column
                index = colData.index(column)
                title = colHeaders[index]
            # Draw title
            self.set_fill_color(200, 220, 220)
            self.cell(colWidth, cellHeight, str(title), align = align, ln = 2, fill = True)
            for count, entry in enumerate(data):
                self.set_fill_color(200, 200, 200)
                if low <= count <= high:
                    filled = True
                else:
                    filled = False
                # Used for writing pass/fail data
                if entry == "PASS":
                    self.set_text_color(0, 255, 0)
                    self.cell(colWidth, cellHeight, "PASS", align = align, ln = 2, fill = filled)
                    self.set_text_color(0, 0, 0)
                elif entry == "FAIL":
                    self.set_text_color(255, 0, 0)
                    self.cell(colWidth, cellHeight, "FAIL", align = align, ln = 2, fill = filled)
                    self.set_text_color(0, 0, 0)
                else:
                    if type(entry) == float:
                        entry = round(entry, 4)
                    self.cell(colWidth, cellHeight, str(entry), align = align, ln = 2, fill = filled)
        self.set_font_size(originalFontSize)
        self.ln(cellHeight)

    def addPlotPage(self, title, imgName, imgSize = 1.0):
        '''@brief Adds a page for tests with outputs consisting only of an image/plot
        @param title Title of test on page
        @param imgName File to save plot as
        @param imgSize Optional, percent of page width image should take up; defaults to 1.0'''
        # Make title
        self.add_page()
        self.set_font('Courier', '', 12)
        self.set_fill_color(200, 220, 220)
        self.cell(0, 6, title, 0, 1, 'L', 1)
        # Make image
        width = imgSize * (self.w - 2 * self.l_margin)
        xpos = (self.w - 2 * self.l_margin) * (1.0 - imgSize) / 2.0
        self.image(imgName, x = xpos, w = width)

    def idleCurrent(self, title, voltages, currents):
        '''@brief Idle current generation test, will be moved to WREBTest.py soon.
        @param title Title of test on page
        @param voltages List of (category title, [voltages])
        @param currents List of (category title, [currents])'''
        self.add_page()
        self.set_font('Courier', '', 12)
        self.set_fill_color(200, 220, 220)
        self.cell(0, 6, title, 0, 1, 'L', 1)
        Vtitles, V = zip(*voltages)
        ITitles, I = zip(*currents)
        self.columnTable([Vtitles, V, ITitles, I],
                         colHeaders = ["Channel", "Voltage", "Channel", "Current"], fontSize = 14)

    def residualTest(self, title, datas, residuals, passed, stats,
                     ROI = None, imgSize = 0.7, xdat = None, pltRange = None):
        '''@brief Report page for tests that consist of a single residual plot, including comments and pass/fail.
        @param title Title of test on page and title of temporary plot image
        @param datas Zipped data arrays and legend titles
        @param residuals Zipped array of residuals and legend titles
        @param passed Pass/fail result of test
        @param stats Relevant comments from the test
        @param ROI Optional parameter specifying region of interest in the plot
        @param imgSize Optional, percent of page width image should take up; defaults to 1.0
        @param xdat Optional zipped array of x values and titles. Defaults to iteration values.
        @param pltRange Optional specified plot range.
        '''
        epw = self.w - 2 * self.l_margin
        self.makeResidualPlotPage(title, "tempFigures/" + title + ".jpg", datas, residuals,
                                  ROI = ROI, imgSize = imgSize, xdat = xdat, pltRange = pltRange)
        self.cell(epw, self.font_size, stats, align = 'C', ln = 1)
        self.passFail(passed)
        self.columnTable(datas + residuals, ROI)

    def makeResidualPlotPage(self, title, imgName, datas, residuals,
                             ROI = None, imgSize = 1.0, xdat = None, pltRange = None):
        '''@brief Generates the new page and plot for the residual tests.
        @param title Title of test on page
        @param imgName Title of temporary plot image
        @param datas Zipped data arrays and legend titles
        @param residuals Zipped array of residuals and legend titles
        @param ROI Optional parameter specifying region of interest in the plot
        @param imgSize Optional, percent of page width image should take up; defaults to 1.0
        @param xdat Optional zipped array of x values and titles. Defaults to iteration values.
        @param pltRange Optional specified plot range.
        '''
        residualPlots(datas, residuals, imgName, ROI = ROI, xdat = xdat, pltRange = pltRange)
        self.addPlotPage(title, imgName, imgSize)

    def makePlotPage(self, title, imgName, datas, imgSize = 1.0, xdat = None):
        '''@brief Generates the new page and plot for the non-residual tests.
        @param title Title of test on page
        @param imgName Title of temporary plot image
        @param datas Zipped data arrays and legend titles
        @param imgSize Optional, percent of page width image should take up; defaults to 1.0
        @param xdat Optional zipped array of x values and titles. Defaults to iteration values.
        '''
        multiPlots(datas, imgName, xdat)
        self.addPlotPage(title, imgName, imgSize)

    def passFail(self, passed):
        '''@brief Return color-coded pass/fail result.
        @param passed String of either "PASS" or "FAIL"'''
        epw = self.w - 2 * self.l_margin
        self.set_fill_color(200, 220, 220)
        if passed == "PASS":
            self.set_text_color(0, 255, 0)
            self.cell(epw, self.font_size, "Test PASSED.", align = 'C', ln = 1, fill = True)
        elif passed == "FAIL":
            self.set_text_color(255, 0, 0)
            self.cell(epw, self.font_size, "Test FAILED.", align = 'C', ln = 1, fill = True)
        self.set_text_color(0, 0, 0)
        self.ln(2 * self.font_size)


if __name__ == "__main__":
    # Example output
    x = np.arange(10)
    a = (range(10), "a")
    b = (2 * np.arange(10), "b")

    # Instantiation of inherited class
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_font('Courier', '', 12)
    title = "Sample test"
    pdf.set_title(title)
    pdf.makeResidualPlotPage(title, "asdf.jpg", [a, b], [a])

    pdf.output('WREBTest.pdf', 'F')
