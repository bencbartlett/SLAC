#!/usr/bin/python
import socket  
import threading
import time
import random
import exceptions


class CcsExecutionResult:
    def __init__(self, thread):
        self.thread = thread;

    def isRunning(self):
        return self.thread.running;

    def getOutput(self):
        while self.thread.running:
            time.sleep(0.1);
        return self.thread.executionOutput;
            

class CcsException(Exception):
    def __init__(self, value):
        self.value = value;
    def __str__(self):
        return repr(self.value);


class CcsJythonInterpreter:
    port = 4444;
    host = None;
    name = None;


    def __init__(self,name=None,host=None,port=4444):
        CcsJythonInterpreter.port = port;
        if host == None:
            CcsJythonInterpreter.host = socket.gethostname() # Get local machine name
        else:
            CcsJythonInterpreter.host = host;
        try:
            self.socketConnection = CcsJythonInterpreter.__establishSocketConnectionToCcsJythonInterpreter__();
            print 'Initialized connection to CCS Python interpreter on on host ', CcsJythonInterpreter.host,':',CcsJythonInterpreter.port;
        except :
            raise CcsException("Could not establish a connection with CCS Python Interpreter on host "+CcsJythonInterpreter.host+":"+str(CcsJythonInterpreter.port));
        
        if name != None :
            name = name.replace("\n","");
            self.syncExecution("initializeInterpreter "+name);

    @staticmethod
    def __establishSocketConnectionToCcsJythonInterpreter__():
         s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
         s.connect((CcsJythonInterpreter.host, CcsJythonInterpreter.port))
         connectionResult = s.recv(4096);
         if "ConnectionRefused" in connectionResult:
            raise CcsException("Connection Refused ");
         return s;



#    def executeScriptFromFile(self, fileName):
#        fo = open(fileName, "r");
#        content = fo.read();
#        result = self.sendInterpreterServer(content);
#        fo.close()
#        return result;

    def aSyncExecution(self, statement, *args):
        return self.sendInterpreterServer(statement, *args);

    def syncExecution(self, statement, *args):
        result = self.sendInterpreterServer(statement, *args);
        output = result.getOutput();
        return result;

    def aSyncScriptExecution(self, fileName, *args):
        fo = open(fileName, "r");
        fileContent = fo.read();
        fo.close();
        return self.sendInterpreterServer(fileContent, *args);

    def syncScriptExecution(self, fileName, *args):
        fo = open(fileName, "r");
        fileContent = fo.read();
        fo.close();
        result = self.sendInterpreterServer(fileContent, *args);
        output = result.getOutput();
        return result;

    def sendInterpreterServer(self, content, *args):

        if len(args) > 0 :
            arguments = "[''";
            for arg in args: 
                arguments += ",'"+str(arg)+"'";
            arguments += "]";
            content = "import sys;\nsys.argv="+arguments+"\n" + content;

        threadId = str(int(round(time.time() * 1000)))+"-"+str(random.randint(0,1000));
        thread = _CcsPythonExecutorThread(threadId,self.socketConnection);
        thread.executePythonContent(content);
        return CcsExecutionResult(thread);



class _CcsPythonExecutorThread:

    def __init__(self, threadId, s):
#        self.s = CcsJythonInterpreter.__establishSocketConnectionToCcsJythonInterpreter__();
        self.s = s;
        self.threadId = threadId;
        self.outputThread = threading.Thread(target=self.listenToSocketOutput);

    def executePythonContent(self,content):
        self.running = True;
        self.outputThread.start();        
        content = "startContent:"+self.threadId+"\n"+content+"\nendContent:"+self.threadId+"\n";
        try:
            self.s.send(content);
        except:
            raise CcsException("Something went wrong with the execution ");
        self.s.send
        return CcsExecutionResult(self);

    def listenToSocketOutput(self):
        self.executionOutput = "";
        while self.running:
            try:
                output = self.s.recv(4096)
            except:
                raise CcsException("Communication Problem with Socket");
            if "doneExecution:"+self.threadId not in output:
#                print output.replace("\n","");
                self.executionOutput += output
            if "doneExecution:"+self.threadId in output:
                self.running = False;
                self.executionOutput = self.executionOutput.replace("doneExecution:"+self.threadId+"\n","");
        self.outputThread._Thread__stop();


 
