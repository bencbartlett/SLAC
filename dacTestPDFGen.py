# PDF Report Generator for dacTest.py
# Ben Bartlett
# 15 June 2016

from fpdf.fpdf import FPDF
import numpy as np
import matplotlib.pyplot as plt 
import time

def residualPlots(datas, residuals, saveAs, xdat = None, pltRange = None):
    '''Generates a set of plots and residuals.
    xvals: zipped x value array and title
    datas: zipped data arrays and legend titles
    residuals: zipped residual arrays and legend titles'''
    if xdat == None:
        xvals = range(len(datas[0][0]))
        xlabel = "Iteration"
    else:
        xvals, xlabel = xdat
    fig1   = plt.figure(1)
    frame1 = fig1.add_axes((.1,.3,.8,.6))
    for data, legtitle in datas:
        plt.plot(xvals, data)
    legendtitles = [legtitle for data, legtitle in datas]
    if pltRange != None:
        plt.ylim(pltRange)
    plt.legend(legendtitles, loc='upper left', prop={'size':8})
    frame1.set_xticklabels([]) #Remove x-tic labels for the first frame
    plt.grid()

    # Residual plot
    frame2 = fig1.add_axes((.1,.1,.8,.2))   
    for data, legtitle in residuals:
        plt.plot(xvals, data,'o')
    legendtitles = [legtitle for data, legtitle in residuals]
    plt.legend(legendtitles, loc='upper left', prop={'size':8})
    plt.xlabel(xlabel)
    plt.grid()
    # Render to image
    fig1.savefig(saveAs)
    plt.close()

def multiPlots(datas, saveAs, xdat = None):
    '''Generates a set of plots and residuals.
    xvals: zipped x value array and title
    datas: zipped data arrays and legend titles'''
    if xdat == None:
        xvals = range(len(datas[0][0]))
        xlabel = "Iteration"
    else:
        xvals, xlabel = xdat
    fig1          = plt.figure(1)
    for data, legtitle in datas:
        plt.plot(xvals, data)
    legendtitles = [legtitle for data, legtitle in datas]
    plt.legend(legendtitles, loc='upper left')
    plt.xlabel(xlabel)
    plt.grid()
    # Render to image
    fig1.savefig(saveAs)
    plt.close()

class PDF(FPDF):
    def header(self):
        # Logo
        self.image('LSSTLogo.jpg', 10, 8, h=15) # For some reason, fpdf doesn't like png's, only jpgs.
        # Arial bold 15
        self.set_font('Arial', 'B', 15)
        # Move to the right
        self.cell(80)
        # Title
        self.cell(30, 10, 'DAC Test: '+time.strftime("%Y-%m-%d %H:%M"), align ='C')
        self.image('SLACLogo.jpg', 150, 8, h=15)
        # Line break
        self.ln(20)

    # Page footer
    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Page number
        self.cell(0, 10, 'Page ' + str(self.page_no()) + '/{nb}', 0, 0, 'C')

    def testTitle(self, title):
        # Arial 12
        self.set_font('Arial', '', 12)
        # Background color
        self.set_fill_color(200, 220, 220)
        # Title
        self.cell(0, 6, title, 0, 1, 'L', 1)
        # Line break
        self.ln(4)

    def summaryPage(self, boardID, testList, passList, statsList):
        self.add_page()
        # Logo
        self.image('LSSTLogo.jpg', 10, 8, h=15) # For some reason, fpdf doesn't like png's, only jpgs.
        # Move to the right
        self.cell(110)
        self.image('SLACLogo.jpg', 150, 8, h=15)
        # Title
        self.set_font('Arial', 'B', 18)
        self.ln(5 * self.font_size)
        epw = self.w - 2*self.l_margin
        self.cell(epw, self.font_size, 'DAC Functional Test Report', align ='C', ln=1)
        self.set_font('Arial', size = 14)
        self.cell(epw, self.font_size, 'Board ID: '+boardID, align ='C', ln=1)
        self.cell(epw, self.font_size, 'Performed: '+time.strftime("%Y-%m-%d %H:%M"), align ='C', ln=1)
        self.ln(2*self.font_size)
        # Summary table
        self.columnTable([passList, testList, statsList], colHeaders = ["Status", "Test", "Results"], fontSize = 12, widthArray = [0.3,1.0,2.0])


    def columnTable(self, colData, colHeaders = None, fontSize = 8, width = 1.0, widthArray = None, align = "L"):
        '''Generates a table from a list of lists of column data. If colHeaders is
        not specified, column data is expected as a tuple like ([data], header),
        as in the plotting functions, else it is expected as a list of titles.
        Width is in % page width the table should occupy. WidthArray is a non-
        normalized list of relative column widths. By default, everything is equal width.'''
        originalFontSize = self.font_size
        self.set_font_size(fontSize) # Small font
        epw         = self.w - 2*self.l_margin
        cellHeight  = self.font_size # Height of cell is equal to font size
        tableStartX = self.get_x()
        tableStartY = self.get_y()  
        if widthArray == None:
            colWidths = width * epw * np.ones(len(colData))/len(colData)
        else:
            colWidths = width * epw * np.array(widthArray) / np.sum(widthArray)
        for column, colWidth in zip(colData, colWidths):
            # Reset the position
            self.set_y(tableStartY)
            self.set_x(tableStartX)
            tableStartX += colWidth

            if colHeaders == None:
                data, title = column
            else:
                data  = column 
                index = colData.index(column)
                title = colHeaders[index]
            # Draw title
            self.set_fill_color(200, 220, 220)
            self.cell(colWidth, cellHeight, str(title), align = align, ln = 2, fill = True)
            for entry in data:
                # Used for writing pass/fail data
                if entry == "PASS":
                    self.set_text_color(0, 255, 0)
                    self.cell(colWidth, cellHeight, "PASS", align = align, ln=2)
                    self.set_text_color(0, 0, 0)
                elif entry == "FAIL":
                    self.set_text_color(255, 0, 0)
                    self.cell(colWidth, cellHeight, "FAIL", align = align, ln=2)
                    self.set_text_color(0, 0, 0)
                else:
                    if type(entry) == float:
                        entry = round(entry, 4)
                    self.cell(colWidth, cellHeight, str(entry), align = align, ln = 2) 
        self.set_font_size(originalFontSize)
        self.ln(cellHeight)


    def addPlotPage(self, title, imgName, imgSize = 1.0):
        '''Tests with outputs consisting only of an image/plot'''
        # Make title
        self.add_page()
        self.set_font('Arial', '', 12)
        self.set_fill_color(200, 220, 220)
        self.cell(0, 6, title, 0, 1, 'L', 1)

        # Make image
        width = imgSize * (self.w - 2*self.l_margin)
        xpos = (self.w - 2*self.l_margin) * (1.0-imgSize)/2.0
        self.image(imgName, x = xpos, w = width)

    def makeResidualPlotPage(self, title, imgName, datas, residuals, imgSize = 1.0, xdat = None, pltRange = None):
        residualPlots(datas, residuals, imgName, xdat, pltRange)
        self.addPlotPage(title, imgName, imgSize)

    def makePlotPage(self, title, imgName, datas, imgSize = 1.0, xdat = None):
        multiPlots(datas, imgName, xdat)
        self.addPlotPage(title, imgName, imgSize)

    def passFail(self, passed):
        epw = self.w - 2*self.l_margin
        if passed == "PASS":
            self.set_text_color(0, 255, 0)
            self.cell(epw, self.font_size, "Test PASSED.", align ='C', ln=1)
        else:
            self.set_text_color(255, 0, 0)
            self.cell(epw, self.font_size, "Test FAILED.", align ='C', ln=1)
        self.set_text_color(0, 0, 0)
        self.ln(2*self.font_size)

    def printTest(self, num, title, name):
        self.add_page()
        self.testTitle(title)
        self.chapter_body(name)

if __name__ == "__main__":
    # Example output
    x = np.arange(10)
    a = (range(10),"a")
    b = (2*np.arange(10),"b")

    # Instantiation of inherited class
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_font('Arial', '', 12)
    title = "Sample test"
    pdf.set_title(title)
    pdf.makeResidualPlotPage(title, "asdf.jpg", [a,b],[a])

    pdf.output('dacTest.pdf', 'F')

