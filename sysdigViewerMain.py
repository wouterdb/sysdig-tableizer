'''
Created on Jul 15, 2014

@author: wouterdb
'''
from itertools import groupby

'''
Created on Aug 16, 2013

@author: wouter
'''
import gi
import time
import sys
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, Gdk
import threading, thread
from datetime import datetime

import collections

GObject.threads_init()

def printFloat(fl):
    return "%.4f" % (fl)

def printInt(fl):
    return "%d" % (fl)



baseFields  = ['evt.cpu','evt.dir','evt.num','evt.time','evt.type','thread.tid']

class GuiServer:
    """This is an Hello World GTK application"""

    def __init__(self,data) :
        # Set the Glade file
        self.gladefile = "mainpane.glade"  
        self.builder = Gtk.Builder()
        self.builder.add_from_file(self.gladefile)
        
        self.window = self.builder.get_object("MainWindow")
        self.window.maximize()
        self.window.show()
        
        
        if (self.window):
            self.window.connect("destroy", Gtk.main_quit)
                    
        #style_provider = Gtk.CssProvider()
        #styledata = open("ui1.css").read()
        #style_provider.load_from_data(styledata)
        #Gtk.StyleContext.add_provider_for_screen(
        #    Gdk.Screen.get_default(),
        #    style_provider,
        #    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        self.rawdata = data
      
        self.collectTypes()

        self.flattenData()
        
        self.buildTableModel()
        self.buildTable()
        
        self.fillAsProcTree()
               
    def collectTypes(self):
        accumulator = collections.defaultdict(lambda:0)

        def collect(line,prefix):
            for (name,val) in line.items():
                myname = prefix + "." + name;
                if isinstance(val, dict):
                    collect(val,myname)
                else:
                    accumulator[myname] = accumulator[myname] +1  
            
        for line in self.rawdata:
            collect(line,"")
        
        items = sorted(accumulator.items(),key=lambda x:x[0], reverse=True)
        #strip count and first . 
        self.fields = [ x[0][1:] for x in items]
    
    def flattenData(self):
        self.data = self.flattenDataInt(self.rawdata)
            
    def flattenDataInt(self,rawdata):
        slotIndex = dict([("."+self.fields[i],i) for i in range(len(self.fields))])
        
        def format(obj):
            out = str(obj)
            if len(out)> 20 :
                out=out[:17] +"..."
            return out
        
        def flatten(line,prefix,record):
            for (name,val) in line.items():
                myname = prefix + "." + name;
                if isinstance(val, dict):
                    flatten(val,myname,record)
                else:
                    record[slotIndex[myname]] = format(val)
            return record  
        
        return [flatten(data,"",[""]*len(self.fields)) for data in rawdata]
        
    def formatfloatcell(self, column, cell, model, iter, user_data):
        cell.set_property('text', printFloat(model.get_value(iter, user_data)))
        
    def formatIntcell(self, column, cell, model, iter, user_data):
        cell.set_property('text', printInt(model.get_value(iter, user_data)))
        
    def formatBoolcell(self, column, cell, model, iter, user_data):
        cell.set_property('active', model.get_value(iter, user_data))
        
    def formatTimeCell(self, column, cell, model, iter, user_data):
        time = datetime.fromtimestamp(model.get_value(iter, user_data)).strftime("%H:%M")
        cell.set_property('text', time)
        
    def buildTableModel(self):
        ncols = len(self.fields)
        cols = [str]*ncols 
        self.datamodel = Gtk.TreeStore(*cols)
         
            
    def buildTable(self):
        names = self.fields
        table = self.builder.get_object("maintable")
        table.set_model(self.datamodel)
        for i in range(len(names)):
            col = Gtk.TreeViewColumn(names[i])
            ren = Gtk.CellRendererText()
            col.pack_start(ren, True)
            col.set_attributes(ren, text=i)
            table.append_column(col)
    
                  
    def setValue(self, name, value):
        GObject.idle_add(self.builder.get_object(name).set_text,value)
        
    def fill(self):
        for line in self.data:
            self.datamodel.append(None,line)
            
    def fillAsProcTree(self):
        slotIndex = dict([(self.fields[i],i) for i in range(len(self.fields))])
        seqIndex = slotIndex["evt.num"]
        
        def sortkey(x):
            thread = x["thread.tid"] 
            time= x["evt.num"]
            return (thread,time)
        
        def groupkey(x):
            return x["thread.tid"] 
        
        mydata = sorted(self.rawdata,key=sortkey)
        
        groups = dict([(x,list(y)) for (x,y) in groupby(mydata,key=groupkey)])
        
        withptid = [x for x in mydata if isinstance(x["evt.args"],dict) ]
        withptid = [x for x in withptid if ("ptid" in x["evt.args"])]
        lineage = [(x["thread.tid"],x["evt.args"]["ptid"][0]) for x in withptid]
        lineageLookup = dict(lineage)
        
        if(len(set(lineage))!=len(set(lineage))):
            print "bad bad, pid with 2 parent pids"
            
        roots = dict()
        
        def findRoot(element,nr):
            if not element:
                return None
            (first,last)=element
            current = first
            while(current!=last):
                next = self.datamodel.iter_next(current)
                if not next:
                    return current
                nextValue = self.datamodel.get_value(next,seqIndex)
                if(int(nextValue)>nr):
                    return current
                current=next
            return last;
        
        def printBlock(tid):
            if(tid in roots):
                return
            
            if(tid in lineageLookup):
                parent =  lineageLookup[tid]
                if not parent in roots:
                    printBlock(parent)
                root = roots[parent]
            else:
                root = None
                
            if not tid in groups:
                #we are above root
                roots[tid]=None
            else:
                block = groups[tid]
                blockFlat = self.flattenDataInt(block)
                myroot=findRoot(root,block[0]["evt.num"])
                first = self.datamodel.append(myroot,blockFlat[0]);
                for line in blockFlat:
                    last = self.datamodel.append(myroot,line)
                roots[tid]=(first,last)
            
        
        
        for tid in groups.keys():
            printBlock(tid)
        
        
        
        
        
            
      
import json
if __name__ == "__main__":
    with open("data") as data:
        hwg = GuiServer(json.loads(data.read()))
        Gtk.main()
     
    



