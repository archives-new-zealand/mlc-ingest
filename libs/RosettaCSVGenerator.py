#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import os
import re
import sys
import uuid
sys.path.append(r'JsonTableSchema/')
import ConfigParser
import JsonTableSchema
from ProvenanceCSVHandlerClass import *
from droidcsvhandlerclass import *
from rosettacsvsectionsclass import RosettaCSVSections

class RosettaCSVGenerator:

   linzcsv = 'linz-xml-data.csv'
   linzlist = []
   AKL = True

   def __init__(self, droidcsv=False, exportsheet=False, rosettaschema=False, configfile=False, provenance=False):
   
      if configfile is not False:
         self.config = ConfigParser.RawConfigParser()
         self.config.read(configfile)   

         if self.config.has_option('application configuration', 'manysips'):
            self.manysips = self.__handle_text_boolean__(self.config.get('application configuration', 'manysips'))
         else:
            self.manysips == False
         
         self.droidcsv = droidcsv
         self.exportsheet = exportsheet
         
         #NOTE: A bit of a hack, compare with import schema work and refactor
         self.rosettaschema = rosettaschema
         self.readRosettaSchema()
         
         #Grab Rosetta Sections
         rs = RosettaCSVSections(configfile)
         self.rosettasections = rs.sections
         
         #set provenance flag and file
         self.prov = False
         if provenance is True:
            self.prov = True
            self.provfile = 'prov.notes'
            if self.config.has_option('provenance', 'file'):
               #Overwrite default, if manually specified...
               self.provfile = self.config.get('provenance', 'file')
          
         self.pathmask = self.__setpathmask__()
      else:
         sys.exit('No config file')
      
      #List duplicate items to check...
      self.duplicateitemsaddedset = set()

   def __handle_text_boolean__(self, boolvalue):
      if boolvalue.lower() == 'true':
         return True
      else:
         return False

   def add_csv_value(self, value):
      field = ''
      if type(value) is int:              #TODO: probably a better way to do this (type-agnostic)
         field = '"' + str(value).replace('\r', '').replace('\n', '')
      else:
         field = '"' + value.encode('utf-8').replace('\r', '').replace('\n', '') + '"'
      return field

   def readRosettaSchema(self):
      f = open(self.rosettaschema, 'rb')
      importschemajson = f.read()
      importschema = JsonTableSchema.JSONTableSchema(importschemajson)
      
      importschemadict = importschema.as_dict()
      importschemaheader = importschema.as_csv_header()

      self.rosettacsvheader = importschemaheader + "\n"  #TODO: Add newline in JSON Handler class? 
      self.rosettacsvdict = importschemadict['fields']
      f.close()

   def createcolumns(self, columno):
      columns = ''
      for column in range(columno):
         columns = columns + '"",'
      return columns

   #NOTE: itemtitle is title from Archway List Control...
   def grabdroidvalue(self, file, field, rosettafield, pathmask):
   
      returnfield = ""            
      droidfield = file[rosettafield]

      if field == 'File Location' or field == 'File Original Path':
         returnfield = os.path.dirname(droidfield).replace(pathmask, '').replace('\\','/') + '/'
      #elif field == 'File Original Path':
      #   returnfield = droidfield.replace(pathmask, '').replace('\\','/')
      else:
         returnfield = droidfield
   
      return returnfield
     
   def csvstringoutput(self, csvlist):   
      #String output...
      csvrows = self.rosettacsvheader

      #TODO: Understand how to get this in rosettacsvsectionclass
      #NOTE: Possibly put all basic RosettaCSV stuff in rosettacsvsectionclass?
      #Static ROW in CSV Ingest Sheet
      if not self.manysips:
         SIPROW = ['"",'] * len(self.rosettacsvdict)
         SIPROW[0] = '"SIP",'
      
         #SIP Title... 
         if self.config.has_option('rosetta mapping', 'SIP Title'):
            SIPROW[1] = '"' + self.config.get('rosetta mapping', 'SIP Title') + '",'
         else:
            SIPROW[1] = '"CSV Load",'
     
         csvrows = csvrows + ''.join(SIPROW).rstrip(',') + '\n'
      
      #write utf-8 BOM
      # NOTE: Don't write UTF-8 BOM... Rosetta doesn't like this. 
      #sys.stdout.write(u'\uFEFF'.encode('utf-8'))
      
      for sectionrows in csvlist:
         rowdata = ""
         for sectionrow in sectionrows:
            for fielddata in sectionrow:
               rowdata = rowdata + fielddata + ','
            rowdata = rowdata.rstrip(',') + '\n'
         csvrows = csvrows + rowdata
      sys.stdout.write(csvrows)
      
      for dupe in self.duplicateitemsaddedset:
         sys.stderr.write("Duplicates to monitor: " + dupe + "\n")

   def __setpathmask__(self):
      pathmask = ''
      if self.config.has_option('path values', 'pathmask'):
         pathmask = self.config.get('path values', 'pathmask')
      return pathmask

   def populaterows(self, field, listcontrolitem, sectionrow, csvindex, rnumber):
   
      #populate cell with static values from config file
      if self.config.has_option('static values', field):
         rosettafield = self.config.get('static values', field)
         if field == 'Revision Number':
            if listcontrolitem == 'PRESERVATION_MASTER':
               sectionrow[csvindex] = self.add_csv_value(rosettafield)
         else:
            sectionrow[csvindex] = self.add_csv_value(rosettafield)
   
      #if there is a mapping configured to the list control, grab the value
      if self.config.has_option('rosetta mapping', field):
         rosettafield = self.config.get('rosetta mapping', field)
         addvalue = listcontrolitem[rosettafield]
         
         #****MULTIPLE ACCESS RESTRICTIONS****#
         #If the field we've got in the config file is Access, we need to
         #Then grab the Rosetta access code for the correct restriction status
         #Following a trail somewhat, but enables more flexible access restrictions in 
         if field == 'Access':
            if self.config.has_option('access values', addvalue):
               #addvalue becomes the specific code given to a specific restriction status...
               addvalue = self.config.get('access values', addvalue)

         sectionrow[csvindex] = self.add_csv_value(addvalue)
         
      #if there is a mapping to a value in the droid export...
      elif self.config.has_option('droid mapping', field):          
         rosettafield = self.config.get('droid mapping', field)         
         sectionrow[csvindex] = self.add_csv_value(self.grabdroidvalue(listcontrolitem, field, rosettafield, self.pathmask))

      else:
         #LINZ Handle REPRESENTATION rows here... 
         if field == 'Preservation Type':
            item = listcontrolitem
            if 'DERIVATIVE_COPY' in item:    #remove PDF and JPG separators
               item = 'DERIVATIVE_COPY'
            sectionrow[csvindex] = self.add_csv_value(item)
         elif field == 'Representation Code':
            if listcontrolitem == 'JPG DERIVATIVE_COPY':
               sectionrow[csvindex] = self.add_csv_value('ANZ_HIGH')
            elif listcontrolitem == 'PDF DERIVATIVE_COPY':
               sectionrow[csvindex] = self.add_csv_value('ANZ_PDF')

         #LINZ Handle FILE rows here...
         elif field == 'File Label':
            extension=listcontrolitem['NAME'][-3:]
            if extension == 'xml':
               filename = listcontrolitem['NAME']
               if re.match("(^R\d{8}-\d{5}.xml$)", filename) is not None:
                  filename = int(filename[10:-4])
                  sectionrow[csvindex] = '"Metadata ' + self.createPageNumberText(listcontrolitem) + '"'
               else:
                  sectionrow[csvindex] = '"Item Metadata"'
            elif extension == 'jp2' or extension == 'tif' or extension == 'TIF':
               if self.AKL == False:
                  sectionrow[csvindex] = self.createPageNumberText(listcontrolitem)
               else:
                  sectionrow[csvindex] = '"Image ' + self.createPageNumberText(listcontrolitem) + '"'
            elif extension == 'jpg':
               filename = listcontrolitem['NAME']
               if re.match("(^R\d{8}-\d{5}.jpg$)", filename) is not None:
                  if self.AKL == False:
                     sectionrow[csvindex] = self.createPageNumberText(listcontrolitem)
                  else:
                     sectionrow[csvindex] = 'Image ' + self.createPageNumberText(listcontrolitem)
               else:
                  sys.stderr.write("Not correct format: " + str(listcontrolitem['FILE_PATH']) + "\n\n")
            elif extension == 'pdf':
               sectionrow[csvindex] = 'Complete File as PDF'
            else:
               #should already be filtered out at this point... 
               sys.stderr.write(str(listcontrolitem['FILE_PATH']) + " not a valid file \n\n")

      return sectionrow

   def createPageNumberText(self, listcontrolitem):   
      label = ''
      if self.AKL == False:
         for item in list(self.linzlist):
            filepath = item['path']
            if listcontrolitem['NAME'][:-4] in filepath[:-4]:   #We won't have duplicate combination of Rnumber-scannumber
               label = item['Proposed Label']
               break
      else:
         label = str(int(listcontrolitem['NAME'].split('-')[1].split('.')[0]))
      return label

   def getRNumbers(self):
      rnumberlist = []
      linzfolders = self.grabFolders()
      for i in linzfolders:
         if i != 'XML' and i != 'DC' and i != 'Masters':
            if re.match("(^R\\d{8}$)", i) is not None:
               #we have something that looks like an R Number use it to populate REPRESENTATION
               rnumberlist.append(i)
            else:
               sys.stderr.write("Error: Unexpected folder in structure, ignoring: " + str(i) + "\n\n")
  
      #for r in rnumberlist:
      #   print r
      #print len(rnumberlist)
      if len(set(rnumberlist)) != len(rnumberlist):
         sys.exit("Error: Duplicates in R-Number list.")
   
      return rnumberlist 
   
   #check to ensure that the files going in are the right extension
   def check_consistency_of_type(self, filename):
      
      #pdf xml jp2 jpg
      if re.match("(^(R\d{8})((-\d{5})?).(xml|jp2|tif|TIF|pdf|jpg)$)", filename) is not None:
         return True
      else:
         sys.stderr.write("Unexpected files in DROID listing: " + str(filename) + "\n")
         return False
    
   
   #Create a list of files belonging to a specific R Number
   def buildfilelist(self, rnumber):
      filelist = []
      for item in list(self.droidlist):   #iterate copy of list to modify original list dynamically
         if rnumber in item['FILE_PATH']:
            if (self.check_consistency_of_type(item['NAME'])):
               filelist.append(item)
            else:
               self.droidlist.remove(item)   #N.b. if we remove it here we lose chance to use it further.
                                             #Remove to free up global memory, speed up as we go.
      
      #sort list for Rosetta appearance... TODO: Consider placement in CSV code.
      #http://stackoverflow.com/questions/72899/how-do-i-sort-a-list-of-dictionaries-by-values-of-the-dictionary-in-python/73050#73050
      #filelist = sorted(filelist, key=lambda k: k['NAME']) #ALTERNATIVE
      
      itemmetadata = '' #retrieve index metadata to insert at front
      #(^R\d{8}.xml$) regex matches item metadata file only. 
      
      for f in list(filelist):
         if re.match("(^R\d{8}.xml$)", f['NAME']) is not None:
            itemmetadata = f
            filelist.remove(f)

      from operator import itemgetter
      filelist = sorted(filelist, key=itemgetter('NAME')) 
      
      if itemmetadata != '':   #we get this for items not in LC (double-check)
         filelist.insert(0, itemmetadata)
            
      return filelist
   
   def buildreplist(self, filelist):
      repdivision = {'PRESERVATION_MASTER': [], 'PDF DERIVATIVE_COPY': [], 'JPG DERIVATIVE_COPY': []}
      for item in filelist:
         #sys.stderr.write(str(item['FILE_PATH'] + "\n"))
         if "XML" in item['FILE_PATH'] or "Masters" in item['FILE_PATH']:
            repdivision['PRESERVATION_MASTER'].append(item)
         elif "DC" in item['FILE_PATH']:
            if item['FILE_PATH'][-3:] == 'jpg':
               repdivision['JPG DERIVATIVE_COPY'].append(item)
            elif item['FILE_PATH'][-3:] == 'pdf':
               repdivision['PDF DERIVATIVE_COPY'].append(item)
      return repdivision
   
   def createrosettacsv(self):      
      self.subseriesmask = ''
      
      #if self.duplicates:
      #   if self.config.has_option('path values', 'subseriesmask'):
      #      self.subseriesmask = self.config.get('path values', 'subseriesmask')
      #   else:
      #      sys.stderr.write("We have duplicate checksums, ensure they don't align with duplicate filenames")  
            
      CSVINDEXSTARTPOS = 2
      csvindex = CSVINDEXSTARTPOS
      
      #we're going to create a new IE per R-Number
      self.rnumber = 0
      self.lastrnumber = False
      
      fields = []
      
      self.lastrnumber = 0
      rnumberlist = self.getRNumbers()
      IECount = 0
      
      
      for item in self.exportlist:

         itemfixity = False
         itemoriginalpath = False
      
         itemrow = []
         rnumber = item['Item Code']     

         if rnumber not in rnumberlist:
            sys.stderr.write("List control item not in DROID list: " + str(rnumber) + "\n")
         else:
            #we've an R number that we care about, let's work with it... 
            IECount += 1
            if rnumber != self.lastrnumber:
               self.lastrnumber = self.rnumber
               self.rnumber = rnumber

               if self.manysips:
                  SIPROW = ['"",'] * len(self.rosettacsvdict)
                  SIPROW[0] = '"SIP"'
               
                  #SIP Title... 
                  if self.config.has_option('rosetta mapping', 'SIP Title'):
                     SIPROW[1] = '"' + self.config.get('rosetta mapping', 'SIP Title') + " " + str(IECount).zfill(4) + '"'
                  else:
                     SIPROW[1] = '"CSV Load",'
                  
                  #csvrows = csvrows + ''.join(SIPROW).rstrip(',') + '\n'
                  itemrow.append(SIPROW)

               #create IE row
               #section row is entire length of x-axis in spreadsheet from CSV JSON Config file...
               sectionrow = ['""'] * len(self.rosettacsvdict)
               
               #Add key to the Y-axis of spreadsheet from dict...
               sectionrow[0] = self.add_csv_value('IE')
               
               for iefield in self.rosettasections[0]['IE']:
                  self.populaterows(iefield, item, sectionrow, csvindex, self.rnumber)
                  csvindex+=1

               #after IE we need to put the files in, plus two representation rows
               #populate a list of r number rows...
               filelist = self.buildfilelist(self.rnumber)  #files belonging to an R Number
               replist = self.buildreplist(filelist)        #Separate into representations
         
               #IE done, add to sheet, remove R-Number
               itemrow.append(sectionrow)
               rnumberlist.remove(rnumber)
               
               #create REPRESENTATION
               for item in replist:
                  #reset CSVINDEX
                  repindex=csvindex

                  #create REPRESENTATION row
                  #section row is entire length of x-axis in spreadsheet from CSV JSON Config file...
                  sectionrow = ['""'] * len(self.rosettacsvdict)
                  sectionrow[0] = self.add_csv_value('REPRESENTATION')
                  
                  
                  
                  #handle REPRESENTATION population...
                  #item in REPLIST = PRESERVATION_MASTER, DERIVATIVE, etc. Greater control.
                  for repfield in self.rosettasections[1]['REPRESENTATION']:
                     self.populaterows(repfield, item, sectionrow, repindex, self.rnumber)
                     repindex+=1
                  
                  itemrow.append(sectionrow)
   
                  fileindex=repindex
                  #FILES HERE...
                  for file in replist[item]:
                     fileindex=repindex
                     
                     sectionrow = ['""'] * len(self.rosettacsvdict)
                     sectionrow[0] = self.add_csv_value('File')
                     
                     for filefield in self.rosettasections[2]['File']:
                        self.populaterows(filefield, file, sectionrow, fileindex, self.rnumber)
                        fileindex+=1
               
                     itemrow.append(sectionrow)

         #These two always needs to be called together. Can it be done in a function?
         #Member variable? 
         fields.append(itemrow)
         csvindex=CSVINDEXSTARTPOS
            
      sys.stderr.write("DROID count: " + str(len(rnumberlist)) + " IEs output: " + str(IECount) + "\n")
      for r in rnumberlist:
         sys.stderr.write(r + " ")
      self.csvstringoutput(fields)

   #TODO: unit tests for this...
   def listduplicates(self):
      seen = []
      dupe = []
      for row in self.droidlist:
         cs = row['MD5_HASH']
         if cs not in seen:
            seen.append(cs)
         else:
            dupe.append(cs)
      return set(dupe)

   def readExportCSV(self):
      if self.exportsheet != False:
         csvhandler = genericCSVHandler()
         exportlist = csvhandler.csvaslist(self.exportsheet)
         return exportlist
   
   def readDROIDCSV(self):
      if self.droidcsv != False:
         droidcsvhandler = droidCSVHandler()
         droidlist = droidcsvhandler.readDROIDCSV(self.droidcsv)
         droidlist = droidcsvhandler.removefolders(droidlist)
         return droidcsvhandler.removecontainercontents(droidlist)        
   
   def readLINZCSV(self):
      csvhandler = genericCSVHandler()
      linzlist = csvhandler.csvaslist(self.linzcsv)
      return linzlist      
   
   def grabFolders(self):
      if self.droidcsv != False:
         droidcsvhandler = droidCSVHandler()
         folderlist = droidcsvhandler.readDROIDCSV(self.droidcsv)
         folderlist = droidcsvhandler.retrievefoldernames(folderlist)
         return folderlist
   
   def export2rosettacsv(self):
      if self.droidcsv != False and self.exportsheet != False:
         self.droidlist = self.readDROIDCSV()
         self.exportlist = self.readExportCSV()
         self.linzlist = self.readLINZCSV()
         #self.readRosettaSchema()  #NOTE: Moved to constructor... TODO: Refactor
         
         if self.prov is True:
            provhandler = provenanceCSVHandler()
            self.provlist = provhandler.readProvenanceCSV(self.provfile)
            if self.provlist is None:
               self.prov = False
         
         #self.duplicates = self.listduplicates()
         self.createrosettacsv()