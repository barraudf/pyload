#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 3 of the License,
    or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
    See the GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, see <http://www.gnu.org/licenses/>.
    
    @author: mkaay
    @version: v0.3
"""

import sys

from time import sleep, time

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from uuid import uuid4 as uuid

from module.gui.ConnectionManager import *
from module.gui.connector import *
from module.gui.MainWindow import *
from module.gui.PWInputWindow import *
from module.gui.Queue import *
from module.gui.Collector import *
from module.gui.XMLParser import *

class main(QObject):
    def __init__(self):
        """
            main setup
        """
        QObject.__init__(self)
        self.app = QApplication(sys.argv)
        self.init()
    
    def init(self):
        self.mainWindow = MainWindow()
        self.pwWindow = PWInputWindow()
        self.connWindow = ConnectionManager()
        self.connector = connector()
        self.mainloop = self.Loop(self)
        self.connectSignals()
        self.parser = XMLParser("module/config/gui.xml", "module/config/gui_default.xml")
        
        self.refreshConnections()
        self.connData = None
        self.connWindow.show()
    
    def startMain(self):
        self.connector.start()
        sleep(1)
        self.mainWindow.show()
        self.initQueue()
        self.initPackageCollector()
        self.initLinkCollector()
        self.mainloop.start()
    
    def stopMain(self):
        self.mainloop.stop()
        self.connector.stop()
        self.mainWindow.hide()
        self.queue.stop()
        self.mainloop.wait()
        self.connector.wait()
        self.queue.wait()
    
    def connectSignals(self):
        """
            signal and slot stuff, yay!
        """
        self.connect(self.connector, SIGNAL("error_box"), self.slotErrorBox)
        self.connect(self.connWindow, SIGNAL("saveConnection"), self.slotSaveConnection)
        self.connect(self.connWindow, SIGNAL("removeConnection"), self.slotRemoveConnection)
        self.connect(self.connWindow, SIGNAL("connect"), self.slotConnect)
        self.connect(self.pwWindow, SIGNAL("ok"), self.slotPasswordTyped)
        self.connect(self.pwWindow, SIGNAL("cancel"), self.quit)
        self.connect(self.mainWindow, SIGNAL("connector"), self.slotShowConnector)
        self.connect(self.mainWindow, SIGNAL("addLinks"), self.slotAddLinks)
    
    def slotShowConnector(self):
        self.stopMain()
        self.init()
    
    def quit(self):
        self.app.quit()
    
    def loop(self):
        """
            start exec loop
        """
        sys.exit(self.app.exec_())
    
    def slotErrorBox(self, msg):
        """
            display a nice error box
        """
        QMessageBox(QMessageBox.Warning, "Error", msg)
    
    def initPackageCollector(self):
        view = self.mainWindow.tabs["collector"]["package_view"]
        view.setColumnCount(1)
        view.setHeaderLabels(["Name"])
        self.packageCollector = PackageCollector(view, self.connector)
        self.packageCollector.start()
    
    def initLinkCollector(self):
        view = self.mainWindow.tabs["collector"]["link_view"]
        view.setColumnCount(1)
        view.setHeaderLabels(["Name"])
        self.linkCollector = LinkCollector(view, self.connector)
        self.linkCollector.start()
    
    def initQueue(self):
        view = self.mainWindow.tabs["queue"]["view"]
        view.setColumnCount(3)
        view.setHeaderLabels(["Name", "Status", "Fortschritt"])
        view.setColumnWidth(0, 300)
        view.setColumnWidth(1, 200)
        view.setColumnWidth(2, 100)
        self.queue = Queue(view, self.connector)
        delegate = QueueProgressBarDelegate(view, self.queue)
        view.setItemDelegateForColumn(2, delegate)
        self.queue.start()
    
    def refreshServerStatus(self):
        status = self.connector.getServerStatus()
        if status["pause"]:
            status["status"] = "Paused"
        else:
            status["status"] = "Running"
        status["speed"] = int(status["speed"])
        text = "Status: %(status)s | Speed: %(speed)s kb/s" % status
        self.mainWindow.serverStatus.setText(text)
    
    def getConnections(self):
        connectionsNode = self.parser.xml.elementsByTagName("connections").item(0)
        if connectionsNode.isNull():
            raise Exception("null")
        connections = self.parser.parseNode(connectionsNode)
        ret = []
        for conn in connections:
            data = {}
            data["type"] = conn.attribute("type", "remote")
            data["default"] = conn.attribute("default", "False")
            data["id"] = conn.attribute("id", uuid().hex)
            if data["default"] == "True":
                data["default"] = True
            else:
                data["default"] = False
            subs = self.parser.parseNode(conn, "dict")
            if not subs.has_key("name"):
                data["name"] = "Unnamed"
            else:
                data["name"] = subs["name"].text()
            if data["type"] == "remote":
                if not subs.has_key("server"):
                    continue
                else:
                    data["host"] = subs["server"].text()
                    data["ssl"] = subs["server"].attribute("ssl", "False")
                    if data["ssl"] == "True":
                        data["ssl"] = True
                    else:
                        data["ssl"] = False
                    data["user"] = subs["server"].attribute("user", "admin")
                    data["port"] = int(subs["server"].attribute("port", "7227"))
            ret.append(data)
        return ret
    
    def slotSaveConnection(self, data):
        connectionsNode = self.parser.xml.elementsByTagName("connections").item(0)
        if connectionsNode.isNull():
            raise Exception("null")
        connections = self.parser.parseNode(connectionsNode)
        connNode = self.parser.xml.createElement("connection")
        connNode.setAttribute("default", str(data["default"]))
        connNode.setAttribute("type", data["type"])
        connNode.setAttribute("id", data["id"])
        nameNode = self.parser.xml.createElement("name")
        nameText = self.parser.xml.createTextNode(data["name"])
        nameNode.appendChild(nameText)
        connNode.appendChild(nameNode)
        if data["type"] == "remote":
            serverNode = self.parser.xml.createElement("server")
            serverNode.setAttribute("ssl", data["ssl"])
            serverNode.setAttribute("user", data["user"])
            serverNode.setAttribute("port", data["port"])
            hostText = self.parser.xml.createTextNode(data["host"])
            serverNode.appendChild(hostText)
            connNode.appendChild(serverNode)
        found = False
        for c in connections:
            cid = c.attribute("id", "None")
            if str(cid) == str(data["id"]):
                found = c
                break
        if found:
            connectionsNode.replaceChild(connNode, found)
        else:
            connectionsNode.appendChild(connNode)
        self.parser.saveData()
        self.refreshConnections()
    
    def slotRemoveConnection(self, data):
        connectionsNode = self.parser.xml.elementsByTagName("connections").item(0)
        if connectionsNode.isNull():
            raise Exception("null")
        connections = self.parser.parseNode(connectionsNode)
        found = False
        for c in connections:
            cid = c.attribute("id", "None")
            if str(cid) == str(data["id"]):
                found = c
                break
        if found:
            connectionsNode.removeChild(found)
        self.parser.saveData()
        self.refreshConnections()
    
    def slotConnect(self, data):
        self.connWindow.hide()
        self.connData = data
        if data["type"] == "local":
            self.slotPasswordTyped("")
        else:
            self.pwWindow.show()
    
    def slotPasswordTyped(self, pw):
        data = self.connData
        data["password"] = pw
        if not data["type"] == "remote":
            coreparser = XMLParser("module/config/core.xml")
            sections = coreparser.parseNode(coreparser.root, "dict")
            conf = coreparser.parseNode(sections["remote"], "dict")
            ssl = coreparser.parseNode(sections["ssl"], "dict")
            data["port"] = conf["port"].text()
            data["user"] = conf["username"].text()
            data["password"] = conf["password"].text()
            data["host"] = "127.0.0.1"
            if str(ssl["activated"].text()).lower() == "true":
                data["ssl"] = True
            else:
                data["ssl"] = False
        if data["ssl"]:
            data["ssl"] = "s"
        else:
            data["ssl"] = ""
        server_url = "http%(ssl)s://%(user)s:%(password)s@%(host)s:%(port)s/" % data
        self.connector.setAddr(server_url)
        self.startMain()
    
    def refreshConnections(self):
        self.parser.loadData()
        conns = self.getConnections()
        self.connWindow.emit(SIGNAL("setConnections(connections)"), conns)
    
    def slotAddLinks(self, links):
        self.connector.addURLs(links)
    
    class Loop(QThread):
        def __init__(self, parent):
            QThread.__init__(self)
            self.parent = parent
            self.running = True
        
        def run(self):
            while self.running:
                sleep(1)
                self.update()
        
        def update(self):
            self.parent.refreshServerStatus()
        
        def stop(self):
            self.running = False

if __name__ == "__main__":
    app = main()
    app.loop()
