# -*- coding: utf-8 -*-

# Adaptation of script from:
# http://norman.walsh.name/2009/11/01/evernote

import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.type.ttypes as Types
import evernote.edam.error.ttypes as Errors
import sys 
from datetime import datetime
import os
from xml.sax.saxutils import escape
from lxml import etree
import ConfigParser


# Utility funtions
def toHex(bits):
  hexv = ""
  for ch in bits:
    h = hex(ord(ch))[2:]
    if len(h) == 1:
      h = "0" + h
    hexv = hexv + h
  return hexv

def toDate(value):
  if value is not None:
    str = datetime.fromtimestamp(value / 1000)
    return str.isoformat()
  else:
    return ""

def u(string):
  if string:
    return unicode(str(string), "utf8")
  return u"None"


# Load config
filepath = 'config.cfg'
config = ConfigParser.ConfigParser()
config.read(filepath)

# Set up evernote api
authToken = config.get("EVERBACK", "authToken")
evernoteHost = "www.evernote.com"
userStoreUri = "https://" + evernoteHost + "/edam/user"
userStoreHttpClient = THttpClient.THttpClient(userStoreUri)
userStoreProtocol = TBinaryProtocol.TBinaryProtocol(userStoreHttpClient)
userStore = UserStore.Client(userStoreProtocol)

# Check version
versionOK = userStore.checkVersion("Evernote EDAMTest (Python)", UserStoreConstants.EDAM_VERSION_MAJOR, UserStoreConstants.EDAM_VERSION_MINOR)

if not versionOK:
    print "Wrong version!"
    exit(1)

# Authenticate
noteStoreUrl = userStore.getNoteStoreUrl(authToken)
noteStoreHttpClient = THttpClient.THttpClient(noteStoreUrl)
noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
noteStore = NoteStore.Client(noteStoreProtocol)


# create XML document
root = etree.Element('evernote')
xmltags = etree.SubElement(root, "tags")
xmlnotebooks = etree.SubElement(root, "notebooks")


# Get all tags
tags = noteStore.listTags(authToken)
print "Saving " + str(len(tags)) + " tags."
if tags is not None:
  for tag in tags:
    xmltag = etree.Element("tag", name=u(tag.name), 
                                  guid=u(tag.guid), 
                                  parentGuid=u(tag.parentGuid), 
                                  updateSequenceNum=u(tag.updateSequenceNum))
    xmltags.append(xmltag)


# Get all of the notebooks in the user's account
notebooks = noteStore.listNotebooks(authToken)

# Get all notes from all notebooks
for notebook in notebooks:

  # Create node for notebook with all attributes
  xmlnotebook = etree.Element("notebook", name=u(notebook.name), 
                                          guid=u(notebook.guid), 
                                          updateSequenceNum=u(notebook.updateSequenceNum), 
                                          defaultNotebook=u(notebook.defaultNotebook), 
                                          serviceCreated=u(toDate(notebook.serviceCreated)), 
                                          serviceUpdated=u(toDate(notebook.serviceUpdated)), 
                                          published=u(notebook.published))

  if notebook.published is not None:
    publishing = notebook.publishing
    xmlnotebook.set("uri", u(publishing.uri))
    xmlnotebook.set("order", u(publishing.order))
    xmlnotebook.set("ascending", u(publishing.ascending))
    xmlnotebook.set("publicDescription", u(publishing.publicDescription))

  # Get all notes from notebook
  filter = NoteStore.NoteFilter()
  filter.notebookGuid = notebook.guid
  notesList = noteStore.findNotes(authToken, filter, 0, 9999)

  print "Saving " + str(len(notesList.notes)) + " notes from notebook " + noptebook.name + "."
  for note in notesList.notes:

    # Create node for note with all attributes
    xmlnote = etree.Element("note", title=u(note.title),
                                    guid=u(note.guid),
                                    contentHash=u(toHex(note.contentHash)),
                                    contentLength=u(note.contentLength),
                                    created=u(toDate(note.created)),
                                    updated=u(toDate(note.updated)),
                                    deleted=u(toDate(note.deleted)),
                                    active=u(note.active),
                                    updateSequenceNum=u(note.updateSequenceNum))

    if note.attributes is not None:
      attr = note.attributes
      xmlnote.set("subjectDate", u(attr.subjectDate))
      xmlnote.set("latitude", u(attr.latitude))
      xmlnote.set("longitude", u(attr.longitude))
      xmlnote.set("altitude", u(attr.altitude))
      xmlnote.set("author", u(attr.author))
      xmlnote.set("source", u(attr.source))
      xmlnote.set("sourceURL", u(attr.sourceURL))
      xmlnote.set("sourceApplication", u(attr.sourceApplication))

    # Add tags is note is tagged
    if note.tagGuids is not None:
      xmltags = etree.Element("tags")
      for tagGuid in note.tagGuids:
        xmltag = etree.Element("tag", guid=tagGuid)
        xmltags.append(xmltag)
      xmlnote.append(xmltags)

    # Save actual content as node text
    content = noteStore.getNoteContent(authToken, note.guid)
    xmlnote.text = u(content)

    # Check for attachments
    if note.resources is not None:

      # Save description of all attachments in note node
      xmlrsrcs = etree.Element("resources")
      for rsrc in note.resources:
        xmlrsrc = etree.Element("resource", guid=u(rsrc.guid), mime=u(rsrc.mime), updateSequenceNum=u(rsrc.updateSequenceNum))

        if rsrc.attributes is not None:
          attr = rsrc.attributes
          xmlrsrc.set("sourceURL", u(attr.sourceURL))
          xmlrsrc.set("timestamp", u(attr.timestamp))
          xmlrsrc.set("latitude", u(attr.latitude))
          xmlrsrc.set("longitude", u(attr.longitude))
          xmlrsrc.set("altitude", u(attr.altitude))
          xmlrsrc.set("cameraMake", u(attr.cameraMake))
          xmlrsrc.set("cameraModel", u(attr.cameraModel))
          xmlrsrc.set("clientWillIndex", u(attr.clientWillIndex))
          xmlrsrc.set("recoType", u(attr.recoType))
          xmlrsrc.set("fileName", u(attr.fileName))
          xmlrsrc.set("attachment", u(attr.attachment))

        # Download attachments
        if (config.get("EVERBACK", "Download")):
          filename = rsrc.guid + '.' + rsrc.mime[rsrc.mime.find("/")+1:]
          filepath = os.path.join(config.get("EVERBACK", "DataPath"), filename)
          afile = open(filepath, "w")
          afile.write(noteStore.getResourceData(authToken, rsrc.guid))
          afile.close()

        xmlrsrcs.append(xmlrsrc)
      xmlnote.append(xmlrsrcs)
    xmlnotebook.append(xmlnote)
  xmlnotebooks.append(xmlnotebook)

# Save notes as xml file
s = etree.tostring(root, pretty_print=True)
filepath = os.path.join(config.get("EVERBACK", "NotePath"), "notes.xml")
f = open(filepath, "w")
f.write(s)
f.close()



