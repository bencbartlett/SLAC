import time
# import signal
import sys

from PythonBinding import *
from org.lsst.ccs.scripting import *

# Catch abort so previous settings can be restored
# signal.signal(signal.SIGINT, exit)
def exit():
    # Bring back the saved temp config
    print ("\nTests concluded or ^C raised. Restoring saved temp config and exiting...")
    raftsub.synchCommandLine(1000,"loadCategories Rafts:WREB_temp_cfg")
    wreb.synchCommandLine(1000,"loadDacs true")    
    wreb.synchCommandLine(1000,"loadBiasDacs true")    
    wreb.synchCommandLine(1000,"loadAspics true")   
    # sys.exit(0)


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

def idleCurrentConsumption():
    # Idle Current Consumption
    print ("\nIdle  current consumption")
    DigPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.DigPS_V").getResult()   
    DigPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.DigPS_I").getResult()  
    print ("DigPS_V[V]:  %5.2f   DigPS_I[mA]:  %7.2f" % (DigPS_V, DigPS_I) )

    AnaPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.AnaPS_V").getResult() 
    AnaPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.AnaPS_I").getResult()
    print ("AnaPS_V[V]:  %5.2f   AnaPS_I[mA]:  %7.2f" % (AnaPS_V, AnaPS_I) )

    ODPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_V").getResult()
    ODPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_I").getResult()   
    print ("ODPS_V[V]:   %5.2f   ODPS_I[mA]:   %7.2f" % (ODPS_V, ODPS_I) )

    ClkHPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_V").getResult()  
    ClkHPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkHPS_I").getResult()  
    print ("ClkHPS_V[V]: %5.2f   ClkHPS_I[mA]: %7.2f" % (ClkHPS_I, ClkHPS_I) )

    # ClkLPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkLPS_V").getResult()  
    # ClkLPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.ClkLPS_I").getResult()  
    # print ("ClkLPS_V[V]: %5.2f   ClkLPS_I[mA]: %7.2f" % (ClkLPS_V, ClkLPS_I) )

    DphiPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_V").getResult()
    DphiPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_I").getResult()
    print ("DphiPS_V[V]: %5.2f   DphiPS_I[mA]: %7.2f" % (DphiPS_V, DphiPS_I) )

    HtrPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.HtrPS_V").getResult()
    HtrPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.HtrPS_I").getResult()
    print ("HtrPS_V[V]:  %5.2f   HtrPS_I[mA]:  %7.2f" % (HtrPS_V, HtrPS_I) )

def CSGate():
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
        wrebBias.synchCommandLine(1000,"change csGate %d" % CSGdac)
        wreb.synchCommandLine(1000,"loadBiasDacs true")    
        time.sleep(tsoak)
        WREB_OD_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_I").getResult()   
        WREB_ODPS_I = raftsub.synchCommandLine(1000,"readChannelValue WREB.ODPS_I").getResult()      
        print ("\t%5.2f\t%5.2f" % (WREB_OD_I, WREB_ODPS_I))
        # Add to arrays to make plots for report
        CSGV_arr.append(CSGV)
        WREB_OD_I_arr.append(WREB_OD_I)
        WREB_ODPS_I_arr.append(WREB_ODPS_I)
    # Return to report generator
    data = ((CSGV_arr, "CSGV (V)"), (WREB_OD_I_arr, "WREB.OD_I (mA)"), (WREB_ODPS_I_arr, "WREB.ODPS_I (mA)"))
    return data


def PCKRails():
    # PCK rails
    print ("\nrail voltage generation for PCLK test ")
    PCLKDV     = 5 #delta voltage between lower and upper
    PCLKLshV   = -8.0 #sets the offset shift to -8V on the lower
    PCLKUshV   = -2 #PCLKLshV+PCLKDV    #sets the offset shift on the upper
    PCLKLV     = PCLKLshV
    PCLKUV     = PCLKLV+PCLKDV
    PCLKLshDAC = V2SHDAC(PCLKLshV,49.9,20)
    PCLKLdac   = V2DAC(PCLKLV,PCLKLshV,49.9,20)
    PCLKUshDAC = V2SHDAC(PCLKUshV,49.9,20)
    PCLKUdac   = V2DAC(PCLKUV,PCLKUshV,49.9,20)
    wrebDAC.synchCommandLine(1000,"change pclkLowSh %d" % PCLKLshDAC)
    wrebDAC.synchCommandLine(1000,"change pclkLow %d" % PCLKLdac)
    wrebDAC.synchCommandLine(1000,"change pclkHighSh %d" % PCLKUshDAC)  
    wrebDAC.synchCommandLine(1000,"change pclkHigh %d" % PCLKUdac)
    wreb.synchCommandLine(1000,"loadDacs true")    
    print ("-8V and 5V amplitude set  ")
    time.sleep(tsoak)
    print ("PCLKLsh[V]: %5.2f   PCLKUsh[V]: %5.2f   PCLKLsh_DACval[ADU]: %4i   PCLKUsh_DACval[ADU]: %4i " % (PCLKLshV, PCLKUshV, PCLKLshDAC, PCLKUshDAC) )
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
        wrebDAC.synchCommandLine(1000,"change pclkLowSh %d" % PCLKLshDAC)
        wrebDAC.synchCommandLine(1000,"change pclkLow %d" % PCLKLdac)
        wrebDAC.synchCommandLine(1000,"change pclkHighSh %d" % PCLKUshDAC)  
        wrebDAC.synchCommandLine(1000,"change pclkHigh %d" % PCLKUdac)
        wreb.synchCommandLine(1000,"loadDacs true")    
        time.sleep(tsoak) 
        WREB_CKPSH_V  = raftsub.synchCommandLine(1000,"readChannelValue WREB.CKPSH_V").getResult()    
        WREB_DphiPS_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.DphiPS_V").getResult()    
        print ("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" % (WREB_CKPSH_V, WREB_DphiPS_V, (PCLKLV - WREB_CKPSH_V), (PCLKUV - WREB_DphiPS_V)) )
        # Append to arrays
        PCLKLV_arr        .append(PCLKLV)
        PCLKLdac_arr      .append(PCLKLdac)
        PCLKUV_arr        .append(PCLKUV)
        PCLKUdac_arr      .append(PCLKUdac)
        WREB_CKPSH_V_arr  .append(WREB_CKPSH_V)
        WREB_DphiPS_V_arr .append(WREB_DphiPS_V)
        deltaPCLKLV_arr   .append(PCLKLV - WREB_CKPSH_V)
        deltaPCLKUV_arr   .append(PCLKUV - WREB_DphiPS_V)
    data = ((PCLKLV_arr, "PCLKLV (V)"),\
            (PCLKUV_arr, "PCLKUV (V)"),\
            (WREB_CKPSH_V_arr, "WREB.CKPSH_V (V)"), \
            (WREB_DphiPS_V_arr, "WREB.DphiPS_V (V)"))
    residuals = ((deltaPCLKLV_arr, "deltaPCLKLV_arr (V)"), \
                 (deltaPCLKUV_arr, "deltaPCLKUV_arr (V)"))

def SCKRails():
    # SCK rails
    print ("\nrail voltage generation for SCLK test ")
    SCLKDV     = 5 #delta voltage between lower and upper
    SCLKLshV   = -8.5 #sets the offset shift to -8V on the lower
    SCLKUshV   = -2 # SCLKLshV+SCLKDV    #sets the offset shift on the upper
    SCLKLV     = SCLKLshV
    SCLKUV     = SCLKLV+SCLKDV
    SCLKLshDAC = V2SHDAC(SCLKLshV,49.9,20)
    SCLKLdac   = V2DAC(SCLKLV,SCLKLshV,49.9,20)
    SCLKUshDAC = V2SHDAC(SCLKUshV,49.9,20)
    SCLKUdac   = V2DAC(SCLKUV,SCLKUshV,49.9,20)
    wrebDAC.synchCommandLine(1000,"change sclkLowSh %d" % SCLKLshDAC)
    wrebDAC.synchCommandLine(1000,"change sclkLow %d" % SCLKLdac)
    wrebDAC.synchCommandLine(1000,"change sclkHighSh %d" % SCLKUshDAC)  
    wrebDAC.synchCommandLine(1000,"change sclkHigh %d" % SCLKUdac)
    wreb.synchCommandLine(1000,"loadDacs true")    
    print ("-8V and 5V amplitude set  ")
    time.sleep(tsoak)
    print ("SCLKLsh[V]: %5.2f   SCLKUsh[V]: %5.2f   SCLKLsh_DACval[ADU]: %4i   SCLKUsh_DACval[ADU]: %4i " % (SCLKLshV, SCLKUshV, SCLKLshDAC, SCLKUshDAC) )
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
        wrebDAC.synchCommandLine(1000,"change sclkLowSh %d" % SCLKLshDAC)
        wrebDAC.synchCommandLine(1000,"change sclkLow %d" % SCLKLdac)
        wrebDAC.synchCommandLine(1000,"change sclkHighSh %d" % SCLKUshDAC)  
        wrebDAC.synchCommandLine(1000,"change sclkHigh %d" % SCLKUdac)
        wreb.synchCommandLine(1000,"loadDacs true")    
        time.sleep(tsoak) 
        WREB_SCKL_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKL_V").getResult()       
        WREB_SCKU_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.SCKU_V").getResult()   
        print ("\t%5.2f\t%5.2f\t\t%5.2f\t%5.2f" % (WREB_SCKL_V, WREB_SCKU_V, (SCLKLV - WREB_SCKL_V), (SCLKUV - WREB_SCKU_V)) )
        # Append to arrays
        SCLKLV_arr        .append(SCLKLV)
        SCLKLdac_arr      .append(SCLKLdac)
        SCLKUV_arr        .append(SCLKUV)
        SCLKUdac_arr      .append(SCLKUdac)
        WREB_SCKL_V_arr   .append(WREB_SCKL_V)
        WREB_SCKU_V_arr   .append(WREB_SCKU_V)
        deltaSCLKLV_arr   .append(SCLKLV - WREB_SCKL_V)
        deltaSCLKUV_arr   .append(SCLKUV - WREB_SCKU_V)
    data = ((SCLKLV_arr, "SCLKLV (V)"),\
            (SCLKUV_arr, "SCLKUV (V)"),\
            (WREB_SCKL_V_arr, "WREB.SCKL_V (V)"), \
            (WREB_SCKU_V_arr, "WREB.SCKU_V (V)"))
    residuals = ((deltaSCLKLV_arr, "deltaSCLKLV (V)"), \
                 (deltaSCLKUV_arr, "deltaSCLKUV (V)"))

def RGRails():
    # RG rails
    print ("\nrail voltage generation for RG test ")
    RGDV     = 5 #delta voltage between lower and upper
    RGLshV   = -8.5 #sets the offset shift to -8.5V on the lower
    RGUshV   = -2.5 # RGLshV+RGDV    #sets the offset shift on the upper
    RGLV     = RGLshV
    RGUV     = RGLV+RGDV
    RGLshDAC = V2SHDAC(RGLshV,49.9,20)
    RGLdac   = V2DAC(RGLV,RGLshV,49.9,20)
    RGUshDAC = V2SHDAC(RGUshV,49.9,20)
    RGUdac   = V2DAC(RGUV,RGUshV,49.9,20)
    wrebDAC.synchCommandLine(1000,"change rgLowSh %d" % RGLshDAC)
    wrebDAC.synchCommandLine(1000,"change rgLow %d" % RGLdac)
    wrebDAC.synchCommandLine(1000,"change rgHighSh %d" % RGUshDAC)  
    wrebDAC.synchCommandLine(1000,"change rgHigh %d" % RGUdac)
    wreb.synchCommandLine(1000,"loadDacs true")    
    print ("-8V and 5V amplitude set  ")
    time.sleep(tsoak)
    print ("RGLsh[V]: %5.2f   RGUsh[V]: %5.2f   RGLsh_DACval[ADU]: %4i   RGUsh_DACval[ADU]: %4i " % (RGLshV, RGUshV, RGLshDAC, RGUshDAC) )
    print ("RGLV[V]\tRGLV_DAC[ADU]\tRGUV[V]\tRGUV_DAC[ADU]\tWREB.RGL_V[V]\tWREB.RGU_V[V]")
    # Report arrays
    RGLV_arr      = []
    RGLdac_arr    = []
    RGUV_arr      = []
    RGUdac_arr    = []
    WREB_RGL_V_arr = []
    WREB_RGU_V_arr = []
    deltaRGLV_arr = []
    deltaRGUV_arr = []
    for RGLV in step_range(RGLshV, RGLshV+12, 0.5): #step trough the lower rail range
        RGLdac = V2DAC(RGLV,RGLshV,49.9,20)
        RGUV   = RGLV+RGDV #adds the delta voltage to the upper rail
        RGUdac = V2DAC(RGUV,RGUshV,49.9,20)
        print ("%5.2f\t%4i\t%5.2f\t%4i" % (RGLV, RGLdac, RGUV, RGUdac) ),
        wrebDAC.synchCommandLine(1000,"change rgLowSh %d" % RGLshDAC)
        wrebDAC.synchCommandLine(1000,"change rgLow %d" % RGLdac)
        wrebDAC.synchCommandLine(1000,"change rgHighSh %d" % RGUshDAC)  
        wrebDAC.synchCommandLine(1000,"change rgHigh %d" % RGUdac)
        wreb.synchCommandLine(1000,"loadDacs true")    
        time.sleep(tsoak) 
        WREB_RGL_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.RGL_V").getResult()    
        WREB_RGU_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.RGU_V").getResult()    
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
    data = ((RGLV_arr, "RGLV (V)"),\
            (RGUV_arr, "RGUV (V)"),\
            (WREB_RGL_V_arr, "WREB.RGL_V (V)"), \
            (WREB_RGU_V_arr, "WREB.RGU_V (V)"))
    residuals = ((deltaRGLV_arr, "deltaRGLV (V)"), \
                 (deltaRGUV_arr, "deltaRGUV (V)"))

def OG():
    # OG
    print ("\nCCD bias OG voltage test ")
    OGshV = -5.0 # #sets the offset shift to -5V
    OGshDAC = V2SHDAC(OGshV,10,10)
    wrebBias.synchCommandLine(1000,"change ogSh %d" % OGshDAC) 
    wreb.synchCommandLine(1000,"loadBiasDacs true")    
    print ("VOGsh[V]: %5.2f   VOGsh_DACval[ADU]: %4i" % (OGshV, OGshDAC) )
    print ("VOG[V]   VOG_DACval[ADU]   WREB.OG[V]")
    OGV_arr       = []
    OGdac_arr     = []
    WREB_OG_V_arr = []
    delta_OGV_arr = []
    for OGV in step_range(OGshV, OGshV+10, 0.5): 
        OGdac = V2DAC(OGV,OGshV,10,10)
        print ("%5.2f\t%4i" % (OGV, OGdac) ),
        wrebBias.synchCommandLine(1000,"change og %d" % OGdac)
        wreb.synchCommandLine(1000,"loadBiasDacs true")    
        time.sleep(tsoak) 
        WREB_OG_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.OG_V").getResult()      
        print ("\t%5.2f\t\t%5.2f" % (WREB_OG_V, (OGV - WREB_OG_V)) )
        OGV_arr.append(OGV)
        OGdac_arr.append(OGdac)
        WREB_OG_V_arr.append(WREB_OG_V)
        delta_OGV_arr.append(OGV - WREB_OG_V)
    data = ((OGV_arr, "VOG (V)"), \
            (WREB_OG_V_arr, "WREB.OG_V (V)"))
    residuals = ((delta_OGV_arr, "deltaVOG (V)"))

def OD():
    # OD
    print ("\nCCD bias OD voltage test ")
    print ("VOD[V]   VOD_DACval[ADU]   WREB.OD[V]")
    ODV_arr       = []
    ODdac_arr     = []
    WREB_OD_V_arr = []
    delta_ODV_arr = []
    for ODV in step_range(0, 30, 1): 
        ODdac = V2DAC(ODV,0,49.9,10)
        print ("%5.2f\t%4i" % (ODV, ODdac)),
        wrebBias.synchCommandLine(1000,"change od %d" % ODdac)
        wreb.synchCommandLine(1000,"loadBiasDacs true")    
        time.sleep(tsoak) 
        WREB_OD_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.OD_V").getResult()     
        print ("\t%5.2f\t\t%5.2f" % (WREB_OD_V,(ODV - WREB_OD_V)) )
        ODV_arr.append(ODV)
        ODdac_arr.append(ODdac)
        WREB_OD_V_arr.append(WREB_OD_V)
        delta_ODV_arr.append(ODV - WREB_OD_V)
    data = ((ODV_arr, "VOD (V)"), \
            (WREB_OD_V_arr, "WREB.OD_V (V)"))
    residuals = ((delta_ODV_arr, "deltaVOD (V)"))
  
def GD():
    # GD
    print ("\nCCD bias GD voltage test ")
    print ("VGD[V]   VGD_DACval[ADU]   WREB.GD[V]")
    GDV_arr       = []
    GDdac_arr     = []
    WREB_GD_V_arr = []
    delta_GDV_arr = []
    for GDV in step_range(0, 30, 1): 
        GDdac = V2DAC(GDV,0,49.9,10)
        print ("%5.2f\t%4i" % (GDV, GDdac)),
        wrebBias.synchCommandLine(1000,"change gd %d" % GDdac)
        wreb.synchCommandLine(1000,"loadBiasDacs true")    
        time.sleep(tsoak) 
        WREB_GD_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.GD_V").getResult()    
        print ("\t%5.2f\t\t%5.2f" % (WREB_GD_V,(GDV - WREB_GD_V)) )
        GDV_arr.append(GDV)
        GDdac_arr.append(GDdac)
        WREB_GD_V_arr.append(WREB_GD_V)
        delta_GDV_arr.append(GDV - WREB_GD_V)
    data = ((GDV_arr, "VGD (V)"), \
            (WREB_GD_V_arr, "WREB.GD_V (V)"))
    residuals = ((delta_GDV_arr, "deltaVGD (V)"))

def RD():
    # RD
    print ("\nCCD bias RD voltage test ")
    print ("VRD[V]   VRD_DACval[ADU]   WREB.RD[V]")
    RDV_arr       = []
    RDdac_arr     = []
    WREB_RD_V_arr = []
    delta_RDV_arr = []
    for RDV in step_range(0, 30, 1): 
        RDdac = V2DAC(RDV,0,49.9,10)
        print ("%5.2f\t%4i" % (RDV, RDdac)),
        wrebBias.synchCommandLine(1000,"change rd %d" % RDdac)
        wreb.synchCommandLine(1000,"loadBiasDacs true")    
        time.sleep(tsoak) 
        WREB_RD_V = raftsub.synchCommandLine(1000,"readChannelValue WREB.RD_V").getResult()     
        print ("\t%5.2f\t\t%5.2f" % (WREB_RD_V, (RDV - WREB_RD_V)) )
        RDV_arr.append(RDV)
        RDdac_arr.append(RDdac)
        WREB_RD_V_arr.append(WREB_RD_V)
        delta_RDV_arr.append(RDV - WREB_RD_V)
    data = ((RDV_arr, "VRD (V)"), \
            (WREB_RD_V_arr, "WREB.RD_V (V)"))
    residuals = ((delta_RDV_arr, "deltaVRD (V)"))

# --------- Execution ---------
if __name__ == "__main__":
    serno   = 'WREBx'
    dataDir = "/u1/u/wreb/data/scratch"

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

    # Execute desired tests
    idleCurrentConsumption()
    CSGate()
    PCKRails()
    SCKRails()
    RGRails()
    OG()
    OD()
    GD()
    RD()

    # Restore previous settings and exit
    exit()



 



