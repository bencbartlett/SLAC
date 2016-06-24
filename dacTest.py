# DAC Testing Script
# Originally written by Sven Herrmann
# Restructured/augmented by Ben Bartlett (bcb@slac.stanford.edu)

# To run:
# Ensure Jython console is running (./JythonConsole or the bootstrapper program)
# Ensure crRun.sh is running
# Ensure DACs are loaded in the CCS console
# "python dacTest.py [options]"


from __future__ import print_function
import signal
import os
import shutil
from numpy import polyfit
from PythonBinding import *


# Catch abort so previous settings can be restored
signal.signal(signal.SIGINT, exit)
def exit(jy):
    # Bring back the saved temp config
    print ("\nTests concluded or ^C raised. Restoring saved temp config and exiting...")
    jy.do('raftsub.synchCommandLine(1000,"loadCategories Rafts:WREB_temp_cfg")')
    jy.do('wreb.synchCommandLine(1000,"loadDacs true")')    
    jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')    
    jy.do('wreb.synchCommandLine(1000,"loadAspics true")')   


# ---------- Helper functions ----------
def step_range(start, end, step):
    while start <= end:
        yield start
        start += step
def V2SHDAC(volt, Rfb, Rin):
    dac=(volt*4095/5/(-Rfb/Rin))
    if dac > 4095 : dac=4095
    if dac < 0    : dac =0
    return dac
def V2DAC(volt, shvolt, Rfb, Rin):
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
        module = importlib.import_module(module)
        cls = getattr(module, type_)
    return cls(value)

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

def idleCurrentConsumption(jy):
    # Idle Current Consumption
    print ("\nIdle  current consumption")
    DigPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DigPS_V").getResult()')
    DigPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DigPS_I").getResult()')
    print ("DigPS_V[V]:  %5.2f   DigPS_I[mA]:  %7.2f" % (DigPS_V, DigPS_I) )

    AnaPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.AnaPS_V").getResult()')
    AnaPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.AnaPS_I").getResult()')
    print ("AnaPS_V[V]:  %5.2f   AnaPS_I[mA]:  %7.2f" % (AnaPS_V, AnaPS_I) )

    ODPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_V").getResult()')
    ODPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_I").getResult()')
    print ("ODPS_V[V]:   %5.2f   ODPS_I[mA]:   %7.2f" % (ODPS_V, ODPS_I) )

    ClkHPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_V").getResult()')
    ClkHPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_I").getResult()')
    print ("ClkHPS_V[V]: %5.2f   ClkHPS_I[mA]: %7.2f" % (ClkHPS_V, ClkHPS_I) )

    # ClkLPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkLPS_V").getResult()  
    # ClkLPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkLPS_I").getResult()  
    # print ("ClkLPS_V[V]: %5.2f   ClkLPS_I[mA]: %7.2f" % (ClkLPS_V, ClkLPS_I) )

    DphiPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_V").getResult()')
    DphiPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_I").getResult()')
    print ("DphiPS_V[V]: %5.2f   DphiPS_I[mA]: %7.2f" % (DphiPS_V, DphiPS_I) )

    HtrPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.HtrPS_V").getResult()')
    HtrPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.HtrPS_I").getResult()')
    print ("HtrPS_V[V]:  %5.2f   HtrPS_I[mA]:  %7.2f" % (HtrPS_V, HtrPS_I) )

    voltages = [("DigPS_V", DigPS_V), ("AnaPS_V", AnaPS_V), ("ODPS_V", ODPS_V), 
                ("ClkHPS_V", ClkHPS_V), ("DphiPS_V", DphiPS_V), ("HtrPS_V", HtrPS_V)]
    currents = [("DigPS_I", DigPS_I), ("AnaPS_I", AnaPS_I), ("ODPS_I", ODPS_I), 
                ("ClkHPS_I", ClkHPS_I), ("DphiPS_I", DphiPS_I), ("HtrPS_I", HtrPS_I)]
    return voltages, currents


def CSGate(jy):
    # CSGate
    print ("\nCCD bias CSgate voltage test ")
    print ("VCSG[V]   VCSG_DACval[ADU]   WREB.OD_I[mA]")
    # Arrays for report
    CSGV_arr = []
    WREB_OD_I_arr = []
    WREB_ODPS_I_arr = []
    for CSGV in step_range(0, 5, 0.25):
        CSGdac = V2DAC(CSGV,0,1,1e6)
        print ("%5.2f\t%4i" % (CSGV, CSGdac)),
        jy.do('wrebBias.synchCommandLine(1000,"change csGate %d")' % CSGdac)
        jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
        time.sleep(tsoak)
        WREB_OD_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_I").getResult()')
        WREB_ODPS_I = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ODPS_I").getResult()')
        print ("\t%5.2f\t%5.2f" % (WREB_OD_I, WREB_ODPS_I))
        # Add to arrays to make plots for report
        CSGV_arr.append(CSGV)
        WREB_OD_I_arr.append(WREB_OD_I)
        WREB_ODPS_I_arr.append(WREB_ODPS_I)
    # Return to report generator
    data = ((CSGV_arr, "CSGV (V)"), (WREB_OD_I_arr, "WREB.OD_I (mA)"), (WREB_ODPS_I_arr, "WREB.ODPS_I (mA)"))
    return data


def PCKRails(jy):
    # PCK rails
    print ("\nrail voltage generation for PCLK test ")
    PCLKDV     = 5 #delta voltage between lower and upper
    PCLKLshV   = -8.0 #sets the offset shift to -8V on the lower
    PCLKUshV   = -2 #PCLKLshV+PCLKDV    #sets the offset shift on the upper
    PCLKLshDAC = V2SHDAC(PCLKLshV,49.9,20)
    PCLKUshDAC = V2SHDAC(PCLKUshV,49.9,20)
    print ("-8V and 5V amplitude set  ")
    time.sleep(tsoak)
    print ("PCLKLsh[V]: %5.2f   PCLKUsh[V]: %5.2f   PCLKLsh_DACval[ADU]: %4i   PCLKUsh_DACval[ADU]: %4i " %
           (PCLKLshV, PCLKUshV, PCLKLshDAC, PCLKUshDAC) )
    print ("PCLKLV[V]\tPCLKLV_DAC[ADU]\tPCLKUV[V]\tPCLKUV_DAC[ADU]\tWREB.PCLKL_V[V]\tWREB.PCLKU_V[V]")
    # Report arrays
    PCLKLV_arr        = []
    PCLKLdac_arr      = []
    PCLKUV_arr        = []
    PCLKUdac_arr      = []
    WREB_CKPSH_V_arr  = []
    WREB_DphiPS_V_arr = []
    deltaPCLKLV_arr   = []
    deltaPCLKUV_arr   = []
    for PCLKLV in step_range(PCLKLshV, PCLKLshV+12, 0.5):
        PCLKLdac = V2DAC(PCLKLV,PCLKLshV,49.9,20)
        PCLKUV   = PCLKLV+PCLKDV
        PCLKUdac = V2DAC(PCLKUV,PCLKUshV,49.9,20)
        print ("%5.2f\t%4i\t%5.2f\t%4i" % (PCLKLV, PCLKLdac, PCLKUV, PCLKUdac) ),
        jy.do('wrebDAC.synchCommandLine(1000,"change pclkLowSh %d")' % PCLKLshDAC)
        jy.do('wrebDAC.synchCommandLine(1000,"change pclkLow %d")' % PCLKLdac)
        jy.do('wrebDAC.synchCommandLine(1000,"change pclkHighSh %d")' % PCLKUshDAC)
        jy.do('wrebDAC.synchCommandLine(1000,"change pclkHigh %d")' % PCLKUdac)
        jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
        time.sleep(tsoak)
        WREB_CKPSH_V  = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.CKPSH_V").getResult()')
        WREB_DphiPS_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_V").getResult()')
        print ("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
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
    data = ((PCLKLV_arr, "PCLKLV (V)"),
            (PCLKUV_arr, "PCLKUV (V)"),
            (WREB_CKPSH_V_arr, "WREB.CKPSH_V (V)"),
            (WREB_DphiPS_V_arr, "WREB.DphiPS_V (V)"))
    residuals = ((deltaPCLKLV_arr, "deltaPCLKLV_arr (V)"),
                 (deltaPCLKUV_arr, "deltaPCLKUV_arr (V)"))
    return data, residuals


# noinspection PyTupleAssignmentBalance
def SCKRails(jy):
    # SCK rails
    print ("\nrail voltage generation for SCLK test ")
    SCLKDV     = 5 #delta voltage between lower and upper
    SCLKLshV   = -8.5 #sets the offset shift to -8V on the lower
    SCLKUshV   = -2 # SCLKLshV+SCLKDV    #sets the offset shift on the upper
    SCLKLshDAC = V2SHDAC(SCLKLshV,49.9,20)
    SCLKUshDAC = V2SHDAC(SCLKUshV,49.9,20)
    print ("-8V and 5V amplitude set  ")
    time.sleep(tsoak)
    print ("SCLKLsh[V]: %5.2f   SCLKUsh[V]: %5.2f   SCLKLsh_DACval[ADU]: %4i   SCLKUsh_DACval[ADU]: %4i " %
           (SCLKLshV, SCLKUshV, SCLKLshDAC, SCLKUshDAC) )
    print ("SCLKLV[V]\tSCLKLV_DAC[ADU]\tSCLKUV[V]\tSCLKUV_DAC[ADU]\tWREB.SCLKL_V[V]\tWREB.SCLKU_V[V]")
    # Report arrays
    SCLKLV_arr      = []
    SCLKLdac_arr    = []
    SCLKUV_arr      = []
    SCLKUdac_arr    = []
    WREB_SCKL_V_arr = []
    WREB_SCKU_V_arr = []
    deltaSCLKLV_arr = []
    deltaSCLKUV_arr = []
    for SCLKLV in step_range(SCLKLshV, SCLKLshV+12, 0.5):
        SCLKLdac = V2DAC(SCLKLV,SCLKLshV,49.9,20)
        SCLKUV   = SCLKLV+SCLKDV
        SCLKUdac = V2DAC(SCLKUV,SCLKUshV,49.9,20)
        print ("%5.2f\t%4i\t%5.2f\t%4i" % (SCLKLV, SCLKLdac, SCLKUV, SCLKUdac) ),
        jy.do('wrebDAC.synchCommandLine(1000,"change sclkLowSh %d")' % SCLKLshDAC)
        jy.do('wrebDAC.synchCommandLine(1000,"change sclkLow %d")' % SCLKLdac)
        jy.do('wrebDAC.synchCommandLine(1000,"change sclkHighSh %d")' % SCLKUshDAC)
        jy.do('wrebDAC.synchCommandLine(1000,"change sclkHigh %d")' % SCLKUdac)
        jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
        time.sleep(tsoak)
        WREB_SCKL_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKL_V").getResult()')
        WREB_SCKU_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKU_V").getResult()')
        print ("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
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
    data = ((SCLKLV_arr, "SCLKLV (V)"),
            (SCLKUV_arr, "SCLKUV (V)"),
            (WREB_SCKL_V_arr, "WREB.SCKL_V (V)"),
            (WREB_SCKU_V_arr, "WREB.SCKU_V (V)"))
    residuals = ((deltaSCLKLV_arr, "deltaSCLKLV (V)"),
                 (deltaSCLKUV_arr, "deltaSCLKUV (V)"))

    # Give pass/fail result
    passed       = "PASS"
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
    ml, bl = polyfit(SCLKLV_arr, WREB_SCKL_V_arr, 1)
    mu, bu = polyfit(SCLKUV_arr, WREB_SCKU_V_arr, 1)
    stats  = "LV Gain: %f.  UV Gain: %f.  %i/%i points within tolerance." % \
        (ml, mu, totalPoints-numErrors, totalPoints)

    # Pass criterion:
    if numErrors > maxFails or abs(ml - 1.0) > 0.05 or abs(mu - 1.0) > 0.05:
        passed = "FAIL"

    return data, residuals, passed, stats

def divergingSCKRails(jy, amplitude, startV):
    '''Diverging SCK Rails test. Amplitude is half-wave maximum divergence, 
    startV is initial voltage to start LV=UV diverging from.'''
    print ("\nDiverging rail voltage generation for SCLK test ")
    SCLKLshV   = startV - amplitude # Shift to minimum needed voltage, this is added back in later
    SCLKUshV   = startV
    SCLKLshDAC = V2SHDAC(SCLKLshV,49.9,20)
    SCLKUshDAC = V2SHDAC(SCLKUshV,49.9,20)
    jy.do('wrebDAC.synchCommandLine(1000,"change sclkLowSh %d")' % SCLKLshDAC)
    jy.do('wrebDAC.synchCommandLine(1000,"change sclkHighSh %d")' % SCLKUshDAC)
    print ("-8V and 5V amplitude set  ")
    time.sleep(tsoak)
    # print ("SCLKLsh[V]: %5.2f   SCLKUsh[V]: %5.2f   SCLKLsh_DACval[ADU]: %4i   SCLKUsh_DACval[ADU]: %4i " % (SCLKLshV, SCLKUshV, SCLKLshDAC, SCLKUshDAC) )
    print ("SCLKLV[V]\tSCLKLV_DAC[ADU]\tSCLKUV[V]\tSCLKUV_DAC[ADU]\tWREB.SCLKL_V[V]\tWREB.SCLKU_V[V]")
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
    for SCLKDV in step_range(0, amplitude, 0.5):
        SCLKLV = startV - SCLKDV
        SCLKUV = startV + SCLKDV
        SCLKLdac = V2DAC(SCLKLV + amplitude,startV,49.9,20) # Add the amplitude back in
        SCLKUdac = V2DAC(SCLKUV,startV,49.9,20)
        print ("%5.2f\t%4i\t%5.2f\t%4i" % (SCLKLV, SCLKLdac, SCLKUV, SCLKUdac) ),
        jy.do('wrebDAC.synchCommandLine(1000,"change sclkLow %d")' % SCLKLdac)
        jy.do('wrebDAC.synchCommandLine(1000,"change sclkHigh %d")' % SCLKUdac)
        jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
        time.sleep(tsoak)
        WREB_SCKL_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKL_V").getResult()')
        WREB_SCKU_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKU_V").getResult()')
        ClkHPS_I = 0.1*jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_I").getResult()')
        print ("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" %
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
    data = ((SCLKLV_arr, "SCLKLV (V)"),
            (SCLKUV_arr, "SCLKUV (V)"),
            (WREB_SCKL_V_arr, "WREB.SCKL_V (V)"),
            (WREB_SCKU_V_arr, "WREB.SCKU_V (V)"),
            (ClkHPS_I_arr, "ClkHPS_I (10mA)"))
    residuals = ((deltaSCLKLV_arr, "deltaSCLKLV (V)"),
                 (deltaSCLKUV_arr, "deltaSCLKUV (V)"))

    # Give pass/fail result
    passed       = "PASS"
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
    ml, bl = polyfit(SCLKLV_arr, WREB_SCKL_V_arr, 1)
    mu, bu = polyfit(SCLKUV_arr, WREB_SCKU_V_arr, 1)
    stats  = "LV Gain: %f.  UV Gain: %f.  %i/%i points within tolerance." % \
        (ml, mu, totalPoints-numErrors, totalPoints)

    # Pass criterion:
    if numErrors > maxFails or abs(ml - 1.0) > 0.05 or abs(mu - 1.0) > 0.05:
        passed = "FAIL"

    return data, residuals, passed, stats


def RGRails(jy):
    # RG rails
    print ("\nrail voltage generation for RG test ")
    RGDV     = 5 #delta voltage between lower and upper
    RGLshV   = -8.5 #sets the offset shift to -8.5V on the lower
    RGUshV   = -2.5 # RGLshV+RGDV    #sets the offset shift on the upper
    RGLshDAC = V2SHDAC(RGLshV,49.9,20)
    RGUshDAC = V2SHDAC(RGUshV,49.9,20)
    print ("-8V and 5V amplitude set  ")
    time.sleep(tsoak)
    print ("RGLsh[V]: %5.2f   RGUsh[V]: %5.2f   RGLsh_DACval[ADU]: %4i   RGUsh_DACval[ADU]: %4i " %
           (RGLshV, RGUshV, RGLshDAC, RGUshDAC) )
    print ("RGLV[V]\tRGLV_DAC[ADU]\tRGUV[V]\tRGUV_DAC[ADU]\tWREB.RGL_V[V]\tWREB.RGU_V[V]")
    # Report arrays
    RGLV_arr       = []
    RGLdac_arr     = []
    RGUV_arr       = []
    RGUdac_arr     = []
    WREB_RGL_V_arr = []
    WREB_RGU_V_arr = []
    deltaRGLV_arr  = []
    deltaRGUV_arr  = []
    for RGLV in step_range(RGLshV, RGLshV+12, 0.5): #step trough the lower rail range
        RGLdac = V2DAC(RGLV,RGLshV,49.9,20)
        RGUV   = RGLV+RGDV #adds the delta voltage to the upper rail
        RGUdac = V2DAC(RGUV,RGUshV,49.9,20)
        print ("%5.2f\t%4i\t%5.2f\t%4i" % (RGLV, RGLdac, RGUV, RGUdac) ),
        jy.do('wrebDAC.synchCommandLine(1000,"change rgLowSh %d")' % RGLshDAC)
        jy.do('wrebDAC.synchCommandLine(1000,"change rgLow %d")' % RGLdac)
        jy.do('wrebDAC.synchCommandLine(1000,"change rgHighSh %d")' % RGUshDAC)
        jy.do('wrebDAC.synchCommandLine(1000,"change rgHigh %d")' % RGUdac)
        jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
        time.sleep(tsoak)
        WREB_RGL_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RGL_V").getResult()')
        WREB_RGU_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RGU_V").getResult()')
        print ("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" % (WREB_RGL_V, WREB_RGU_V, (RGLV - WREB_RGL_V), (RGUV - WREB_RGU_V)) )
        # Append to arrays
        RGLV_arr        .append(RGLV)
        RGLdac_arr      .append(RGLdac)
        RGUV_arr        .append(RGUV)
        RGUdac_arr      .append(RGUdac)
        WREB_RGL_V_arr  .append(WREB_RGL_V)
        WREB_RGU_V_arr  .append(WREB_RGU_V)
        deltaRGLV_arr   .append(RGLV - WREB_RGL_V)
        deltaRGUV_arr   .append(RGUV - WREB_RGU_V)
    data = ((RGLV_arr, "RGLV (V)"),
            (RGUV_arr, "RGUV (V)"),
            (WREB_RGL_V_arr, "WREB.RGL_V (V)"),
            (WREB_RGU_V_arr, "WREB.RGU_V (V)"))
    residuals = ((deltaRGLV_arr, "deltaRGLV (V)"),
                 (deltaRGUV_arr, "deltaRGUV (V)"))

    # Give pass/fail result
    passed       = "PASS"
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
    ml, bl = polyfit(RGLV_arr, WREB_RGL_V_arr, 1)
    mu, bu = polyfit(RGUV_arr, WREB_RGU_V_arr, 1)
    stats  = "LV Gain: %f.  UV Gain: %f.  %i/%i points within tolerance." % \
        (ml, mu, totalPoints-numErrors, totalPoints)

    # Pass criterion:
    if numErrors > maxFails or abs(ml - 1.0) > 0.05 or abs(mu - 1.0) > 0.05:
        passed = "FAIL"

    return data, residuals, passed, stats

def divergingRGRails(jy, amplitude, startV):
    '''Diverging RG Rails test. Amplitude is half-wave maximum divergence, 
    startV is initial voltage to start LV=UV diverging from.'''
    print ("\nDiverging rail voltage generation for RG test ")
    RGLshV   = startV - amplitude # Shift to minimum needed voltage, this is added back in later
    RGUshV   = startV
    RGLshDAC = V2SHDAC(RGLshV,49.9,20)
    RGUshDAC = V2SHDAC(RGUshV,49.9,20)
    jy.do('wrebDAC.synchCommandLine(1000,"change rgLowSh %d")' % RGLshDAC)
    jy.do('wrebDAC.synchCommandLine(1000,"change rgHighSh %d")' % RGUshDAC)
    print ("-8V and 5V amplitude set  ")
    time.sleep(tsoak)
    # print ("RGLsh[V]: %5.2f   RGUsh[V]: %5.2f   RGLsh_DACval[ADU]: %4i   RGUsh_DACval[ADU]: %4i " % (RGLshV, RGUshV, RGLshDAC, RGUshDAC) )
    print ("RGLV[V]\tRGLV_DAC[ADU]\tRGUV[V]\tRGUV_DAC[ADU]\tWREB.RGL_V[V]\tWREB.RGU_V[V]")
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
    for RGDV in step_range(0, amplitude, 0.5):
        RGLV = startV - RGDV
        RGUV = startV + RGDV
        RGLdac = V2DAC(RGLV + amplitude,startV,49.9,20) # Add the amplitude back in
        RGUdac = V2DAC(RGUV,startV,49.9,20)
        print ("%5.2f\t%4i\t%5.2f\t%4i" % (RGLV, RGLdac, RGUV, RGUdac) ),
        jy.do('wrebDAC.synchCommandLine(1000,"change rgLow %d")' % RGLdac)
        jy.do('wrebDAC.synchCommandLine(1000,"change rgHigh %d")' % RGUdac)
        jy.do('wreb.synchCommandLine(1000,"loadDacs true")')
        time.sleep(tsoak)
        WREB_RGL_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RGL_V").getResult()')
        WREB_RGU_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RGU_V").getResult()')
        ClkHPS_I = 0.1 * jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_I").getResult()')
        print ("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" % (WREB_RGL_V, WREB_RGU_V, (RGLV - WREB_RGL_V), (RGUV - WREB_RGU_V)) )
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
    data = ((RGLV_arr, "RGLV (V)"),
            (RGUV_arr, "RGUV (V)"),
            (WREB_RGL_V_arr, "WREB.RGL_V (V)"),
            (WREB_RGU_V_arr, "WREB.RGU_V (V)"),
            (ClkHPS_I_arr, "ClkHPS_I (10mA)"))
    residuals = ((deltaRGLV_arr, "deltaRGLV (V)"),
                 (deltaRGUV_arr, "deltaRGUV (V)"))

    # Give pass/fail result
    passed       = "PASS"
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
    ml, bl = polyfit(RGLV_arr, WREB_RGL_V_arr, 1)
    mu, bu = polyfit(RGUV_arr, WREB_RGU_V_arr, 1)
    stats  = "LV Gain: %f.  UV Gain: %f.  %i/%i points within tolerance." % \
        (ml, mu, totalPoints-numErrors, totalPoints)

    # Pass criterion:
    if numErrors > maxFails or abs(ml - 1.0) > 0.05 or abs(mu - 1.0) > 0.05:
        passed = "FAIL"

    return data, residuals, passed, stats

def OG(jy):
    # OG
    print ("\nCCD bias OG voltage test ")
    OGshV = -5.0 # #sets the offset shift to -5V
    OGshDAC = V2SHDAC(OGshV,10,10)
    jy.do('wrebBias.synchCommandLine(1000,"change ogSh %d")' % OGshDAC)
    jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
    print ("VOGsh[V]: %5.2f   VOGsh_DACval[ADU]: %4i" % (OGshV, OGshDAC) )
    print ("VOG[V]   VOG_DACval[ADU]   WREB.OG[V]")
    OGV_arr       = []
    OGdac_arr     = []
    WREB_OG_V_arr = []
    deltaOGV_arr = []
    for OGV in step_range(OGshV, OGshV+10, 0.5):
        OGdac = V2DAC(OGV,OGshV,10,10)
        print ("%5.2f\t%4i" % (OGV, OGdac) ),
        jy.do('wrebBias.synchCommandLine(1000,"change og %d")' % OGdac)
        jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
        time.sleep(tsoak)
        WREB_OG_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OG_V").getResult()')
        print ("\t%5.2f\t\t%5.2f" % (WREB_OG_V, (OGV - WREB_OG_V)) )
        OGV_arr.append(OGV)
        OGdac_arr.append(OGdac)
        WREB_OG_V_arr.append(WREB_OG_V)
        deltaOGV_arr.append(OGV - WREB_OG_V)
    data = ((OGV_arr, "VOG (V)"),
            (WREB_OG_V_arr, "WREB.OG_V (V)"))
    residuals = ((deltaOGV_arr, "deltaVOG (V)"),)

    # Give pass/fail result
    passed       = "PASS"
    allowedError = 0.25 # Some arbitrary value giving the allowable residual error
    maxFails     = 2 # Some value giving the maximum number of allowed failures
    numErrors    = 0
    totalPoints  = 0
    for residual in deltaOGV_arr:
        if abs(residual) > allowedError: numErrors += 1
        totalPoints += 1

    # Other information
    m, b  = polyfit(OGV_arr, WREB_OG_V_arr, 1)
    stats = "Gain: %f.  %i/%i points within tolerance." % (m, totalPoints-numErrors, totalPoints)

    # Pass criterion:
    if numErrors > maxFails or abs(m - 1.0) > 0.05:
        passed = "FAIL"

    return data, residuals, passed, stats

def OD(jy):
    # OD
    print ("\nCCD bias OD voltage test ")
    print ("VOD[V]   VOD_DACval[ADU]   WREB.OD[V]")
    ODV_arr       = []
    ODdac_arr     = []
    WREB_OD_V_arr = []
    deltaODV_arr = []
    for ODV in step_range(0, 30, 1):
        ODdac = V2DAC(ODV,0,49.9,10)
        print ("%5.2f\t%4i" % (ODV, ODdac)),
        jy.do('wrebBias.synchCommandLine(1000,"change od %d")' % ODdac)
        jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
        time.sleep(tsoak)
        WREB_OD_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_V").getResult()')
        print ("\t%5.2f\t\t%5.2f" % (WREB_OD_V,(ODV - WREB_OD_V)) )
        ODV_arr.append(ODV)
        ODdac_arr.append(ODdac)
        WREB_OD_V_arr.append(WREB_OD_V)
        deltaODV_arr.append(ODV - WREB_OD_V)
    data = ((ODV_arr, "VOD (V)"),
            (WREB_OD_V_arr, "WREB.OD_V (V)"))
    residuals = ((deltaODV_arr, "deltaVOD (V)"),)

    # Give pass/fail result
    passed       = "PASS"
    allowedError = 0.25 # Some arbitrary value giving the allowable residual error
    maxFails     = 2 # Some value giving the maximum number of allowed failures
    numErrors    = 0
    totalPoints  = 0
    for residual in deltaODV_arr:
        if abs(residual) > allowedError: numErrors += 1
        totalPoints += 1

    # Other information
    m, b  = polyfit(ODV_arr, WREB_OD_V_arr, 1)
    stats = "Gain: %f.  %i/%i points within tolerance." % (m, totalPoints-numErrors, totalPoints)

    # Pass criterion:
    if numErrors > maxFails or abs(m - 1.0) > 0.05:
        passed = "FAIL"

    return data, residuals, passed, stats

def GD(jy):
    # GD
    print ("\nCCD bias GD voltage test ")
    print ("VGD[V]   VGD_DACval[ADU]   WREB.GD[V]")
    GDV_arr       = []
    GDdac_arr     = []
    WREB_GD_V_arr = []
    deltaGDV_arr = []
    for GDV in step_range(0, 30, 1):
        GDdac = V2DAC(GDV,0,49.9,10)
        print ("%5.2f\t%4i" % (GDV, GDdac)),
        jy.do('wrebBias.synchCommandLine(1000,"change gd %d")' % GDdac)
        jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
        time.sleep(tsoak)
        WREB_GD_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.GD_V").getResult()')
        print ("\t%5.2f\t\t%5.2f" % (WREB_GD_V,(GDV - WREB_GD_V)) )
        GDV_arr.append(GDV)
        GDdac_arr.append(GDdac)
        WREB_GD_V_arr.append(WREB_GD_V)
        deltaGDV_arr.append(GDV - WREB_GD_V)
    data = ((GDV_arr, "VGD (V)"),
            (WREB_GD_V_arr, "WREB.GD_V (V)"))
    residuals = ((deltaGDV_arr, "deltaVGD (V)"),)

    # Give pass/fail result
    passed       = "PASS"
    allowedError = 0.25 # Some arbitrary value giving the allowable residual error
    maxFails     = 2 # Some value giving the maximum number of allowed failures
    numErrors    = 0
    totalPoints  = 0
    for residual in deltaGDV_arr:
        if abs(residual) > allowedError: numErrors += 1
        totalPoints += 1

    # Other information
    m, b  = polyfit(GDV_arr, WREB_GD_V_arr, 1)
    stats = "Gain: %f.  %i/%i points within tolerance." % (m, totalPoints-numErrors, totalPoints)

    # Pass criterion:
    if numErrors > maxFails or abs(m - 1.0) > 0.05:
        passed = "FAIL"

    return data, residuals, passed, stats

def RD(jy):
    # RD
    print ("\nCCD bias RD voltage test ")
    print ("VRD[V]   VRD_DACval[ADU]   WREB.RD[V]")
    RDV_arr       = []
    RDdac_arr     = []
    WREB_RD_V_arr = []
    deltaRDV_arr = []
    for RDV in step_range(0, 30, 1):
        RDdac = V2DAC(RDV,0,49.9,10)
        print ("%5.2f\t%4i" % (RDV, RDdac)),
        jy.do('wrebBias.synchCommandLine(1000,"change rd %d")' % RDdac)
        jy.do('wreb.synchCommandLine(1000,"loadBiasDacs true")')
        time.sleep(tsoak)
        WREB_RD_V = jy.get('raftsub.synchCommandLine(1000,"readChannelValue WREB.RD_V").getResult()')
        print ("\t%5.2f\t\t%5.2f" % (WREB_RD_V, (RDV - WREB_RD_V)) )
        RDV_arr.append(RDV)
        RDdac_arr.append(RDdac)
        WREB_RD_V_arr.append(WREB_RD_V)
        deltaRDV_arr.append(RDV - WREB_RD_V)
    data = ((RDV_arr, "VRD (V)"),
            (WREB_RD_V_arr, "WREB.RD_V (V)"))
    residuals = ((deltaRDV_arr, "deltaVRD (V)"),)

    # Give pass/fail result
    passed       = "PASS"
    allowedError = 0.25 # Some arbitrary value giving the allowable residual error
    maxFails     = 2 # Some value giving the maximum number of allowed failures
    numErrors    = 0
    totalPoints  = 0
    for residual in deltaRDV_arr:
        if abs(residual) > allowedError: numErrors += 1
        totalPoints += 1

    # Other information
    m, b  = polyfit(RDV_arr, WREB_RD_V_arr, 1)
    stats = "Gain: %f.  %i/%i points within tolerance." % (m, totalPoints-numErrors, totalPoints)

    # Pass criterion:
    if numErrors > maxFails or abs(m - 1.0) > 0.05:
        passed = "FAIL"

    return data, residuals, passed, stats

# --------- Execution ---------
if __name__ == "__main__":
    # Argument parser
    import argparse
    parser = argparse.ArgumentParser(description =
        '''Test script for DAC on CCD controller boards to generate a pdf status report.''',
                                     epilog = '''>> Example: python dacTest.py ~/u1/u/wreb/data -q''')
    parser.add_argument("writeDirectory", nargs = '?', default = "/u1/u/wreb/data/scratch",
                        help="Directory to save outputs to. Defaults to /u1/u/wreb/data/scratch.", action="store")
    parser.add_argument("-q", "--quiet",
                        help="Suppress text output.", action="store_true")
    parser.add_argument("-n", "--noPDF",
                        help="Do not render a PDF report for the tests.", action="store_true")
    args = parser.parse_args()


    tsoak = 0.5
    dataDir = args.writeDirectory

    jy = JythonInterface()
    jy.do('dataDir = %s'%args.writeDirectory)

    jy.do('''
from org.lsst.ccs.scripting import *
import time
import sys

serno   = "WREBx"

raftsub  = CCS.attachSubsystem("ccs-cr");
wreb     = CCS.attachSubsystem("ccs-cr/WREB")
wrebDAC  = CCS.attachSubsystem("ccs-cr/WREB.DAC")
wrebBias = CCS.attachSubsystem("ccs-cr/WREB.Bias0")


tsoak = 0.5
# save config inside the board to temp_cfg and load the test_base_cfg
print ("saving board configuration and set up test configuration and sequence")
raftsub.synchCommandLine(1000,"saveChangesForCategoriesAs Rafts:WREB_temp_cfg")
raftsub.synchCommandLine(1000,"loadCategories Rafts:WREB_test_base_cfg")
wreb.synchCommandLine(1000,"loadDacs true")
wreb.synchCommandLine(1000,"loadBiasDacs true")
wreb.synchCommandLine(1000,"loadAspics true")
# load a sequence and run it with 0s exposure time
raftsub.synchCommandLine(1000,"loadSequencer  /u1/u/wreb/rafts/xml/wreb_ITL_20160419.seq")
raftsub.synchCommandLine(1000,"setParameter Exptime 0");  # sets exposure time to 0ms
time.sleep(tsoak)
raftsub.synchCommandLine(1000,"startSequencer")
time.sleep(2.5) #takes 2 sec to read out
# save the bias image under this:
fbase = "%s_test" % (serno)
fname = fbase + "_${timestamp}.fits"
raftsub.synchCommandLine(1000, "setFitsFileNamePattern " + fname)
# result = raftsub.synchCommand(1000,"saveFitsImage " + dataDir)
# print ("save fits file under: %s" % (dataDir))
# print result.getResult()
    ''')

    boardID = "TEST"  # hex(jy.get('wreb.synchCommandLine getSerialNumber', dtype = 'int')) # Get hex board ID

    if not os.path.exists("tempFigures"):
        os.makedirs("tempFigures")

    # Instantiation of inherited class
    from dacTestPDFGen import *

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_font('Arial', '', 12)
    epw = pdf.w - 2 * pdf.l_margin

    # Execute desired tests
    idleCurrentConsumption(jy)

    testList = ["SCK Rails", "CCD Bias OG Voltage", "CCD Bias OD Voltage", "CCD Bias GR Voltage",
                "CCD Bias RD Voltage"]
    passList = []
    statsList = []

    _, _, passed, stats = divergingSCKRailsResults0 = divergingSCKRails(jy, 9.0, 0.0)
    _, _, passed, stats = divergingSCKRailsResults3 = divergingSCKRails(jy, 9.0, 3.0)
    _, _, passed, stats = divergingSCKRailsResultsm3 = divergingSCKRails(jy, 9.0, -3.0)

    _, _, passed, stats = divergingRGRailsResults0 = divergingRGRails(jy, 9.0, 0.0)
    _, _, passed, stats = divergingRGRailsResults3 = divergingRGRails(jy, 9.0, 3.0)
    _, _, passed, stats = divergingRGRailsResultsm3 = divergingRGRails(jy, 9.0, -3.0)

    CSGateResults = CSGate(jy)
    PCKRailsResults = PCKRails(jy)
    # _,_,passed,stats = CSGateResults   = CSGate(jy);   passList.append(passed); statsList.append(stats)
    # _,_,passed,stats = PCKRailsResults = PCKRails(jy); passList.append(passed); statsList.append(stats)
    _, _, passed, stats = SCKRailsResults = SCKRails(jy) ; passList.append(passed) ; statsList.append(stats)
    _, _, passed, stats = RGRailsResults = RGRails(jy)   ; passList.append(passed) ; statsList.append(stats)
    _, _, passed, stats = OGResults = OG(jy)             ; passList.append(passed) ; statsList.append(stats)
    _, _, passed, stats = ODResults = OD(jy)             ; passList.append(passed) ; statsList.append(stats)
    _, _, passed, stats = GDResults = GD(jy)             ; passList.append(passed) ; statsList.append(stats)
    _, _, passed, stats = RDResults = RD(jy)             ; passList.append(passed) ; statsList.append(stats)

    # Generate summary page
    pdf.summaryPage(boardID, testList, passList, statsList)

    # CS Gate Test
    data = CSGateResults
    pdf.makePlotPage("CSGate Test", "CSGate.jpg", data)
    pdf.columnTable(data)

    # PCK Rails Test
    data, residuals = PCKRailsResults
    pdf.makeResidualPlotPage("PCKRails Test", "tempFigures/PCKRails.jpg", data, residuals)

    # SCK Rails Test
    pdf.residualTest(*(("SCK Rails Test",) + SCKRailsResults))

    # RG Rails
    pdf.residualTest(*(("RG Rails Test",) + RGRailsResults))

    # SCK Diverging Rails Test
    for testResults in [divergingSCKRailsResults0, divergingSCKRailsResults3, divergingSCKRailsResultsm3]:
        data, residuals, passed, stats = testResults
        pdf.makeResidualPlotPage("Diverging SCKRails Test 0V", "tempFigures/divergingSCKRails0.jpg", data, residuals,
                                 pltRange = [-12, 12])
        pdf.cell(epw, pdf.font_size, stats, align = 'C', ln = 1)
        pdf.passFail(passed)
        pdf.columnTable(data + residuals)

    # RG Diverging Rails Test
    for testResults in [divergingRGRailsResults0, divergingRGRailsResults3, divergingRGRailsResultsm3]:
        data, residuals, passed, stats = testResults
        pdf.makeResidualPlotPage("Diverging RGRails Test 0V", "tempFigures/divergingRGRails0.jpg", data, residuals,
                                 pltRange = [-12, 12])
        pdf.cell(epw, pdf.font_size, stats, align = 'C', ln = 1)
        pdf.passFail(passed)
        pdf.columnTable(data + residuals)

    # OG Test
    pdf.residualTest(*(("OG Bias Test",) + OGResults))

    # OD Test
    pdf.residualTest(*(("OD Bias Test",) + ODResults))

    # GD Test
    pdf.residualTest(*(("GD Bias Test",) + GDResults))

    # RD Test
    pdf.residualTest(*(("RD Bias Test",) + RDResults))

    if not args.noPDF:
        print("Generating PDF report at " + dataDir + '/dacTest.pdf')
        pdf.output(dataDir + '/dacTest.pdf', 'F')

    shutil.rmtree("tempFigures")

    # Restore previous settings and exit
    exit(jy)




