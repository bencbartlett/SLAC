# PDF Report Generator for dacTest.py
# Ben Bartlett
# 15 June 2016

from fpdf.fpdf import FPDF
import numpy as np
import matplotlib.pyplot as plt 
import time

def residualPlots(datas, residuals, saveAs, xdat = None):
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
    plt.legend(legendtitles, loc='upper left')
    frame1.set_xticklabels([]) #Remove x-tic labels for the first frame
    plt.grid()

    # Residual plot
    frame2 = fig1.add_axes((.1,.1,.8,.2))   
    for data, legtitle in residuals:
        plt.plot(xvals, data,'o')
    legendtitles = [legtitle for data, legtitle in residuals]
    plt.legend(legendtitles, loc='upper left')
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

    def testBody(self, name):
        # Read text file
        with open(name, 'rb') as fh:
            txt = fh.read().decode('latin-1')
        # Times 12
        self.set_font('Times', '', 12)
        # Output justified text
        self.multi_cell(0, 5, txt)
        # Line break
        self.ln()
        # Mention in italics
        self.set_font('', 'I')
        self.cell(0, 5, '(end of excerpt)')

    def addImgTest(self, title, imgName):
        '''Tests with outputs consisting only of an image/plot'''
        # Make title
        self.add_page()
        self.set_font('Arial', '', 12)
        self.set_fill_color(200, 220, 220)
        self.cell(0, 6, title, 0, 1, 'L', 1)
        self.ln(4)

        # Make image
        self.image(imgName, w=195)

    def makeResidualImagePage(self, title, imgName, datas, residuals, xdat = None):
        residualPlots(datas, residuals, imgName, xdat)
        self.addImgTest(title, imgName)

    def makeImagePage(self, title, imgName, datas, xdat = None):
        multiPlots(datas, imgName, xdat)
        self.addImgTest(title, imgName)

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
    pdf.makeResidualImagePage(title, "asdf.jpg", [a,b],[a])

    pdf.output('dacTest.pdf', 'F')