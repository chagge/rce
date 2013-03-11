#!/usr/bin/env python
# -*- coding: utf-8 -*-
#     
#     connection.py
#     
#     This file is part of the RoboEarth Cloud Engine pyrce client.
#     
#     This file was originally created for RoboEearth
#     http://www.roboearth.org/
#     
#     The research leading to these results has received funding from
#     the European Union Seventh Framework Programme FP7/2007-2013 under
#     grant agreement no248942 RoboEarth.
#     
#     Copyright 2012 RoboEarth
#     
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#     
#     http://www.apache.org/licenses/LICENSE-2.0
#     
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#     
#     \author/s: Dhananjay Sathe, Mayank Singh
#     
#     

# Python specific imports
import sys
from uuid import uuid4
from multiprocessing.managers import SyncManager
from collections import defaultdict

#zope specific imports
from zope.interface import implements

#twisted specific imports
from twisted.internet import defer
from twisted.cred.portal import IRealm, Portal
from twisted.spread.pb import IPerspective, PBServerFactory, Avatar

#rce specific imports
from rce.error import InternalError


class InterfaceConnection2way(dict):
    def __init__(self, d=None):
        dict.__init__(self)
        self.d1 = defaultdict(list)
        self.d2 = defaultdict(list)

    def __getitem__(self, key):
        try:
            return self.d1.get(key)
        except KeyError:
            return self.d2(key)

    def __setitem__(self, key, val):
        self.d1[key].append(val)
        self.d2[val].append(key)

    def key(self, val):
        return self.d2[val]

    def keys(self, val):
        return self.d2.keys()

    def iterkeys(self, val):
        return self.d2.iterkeys()

    def get(self, key):
        return self.d1[key]

    def values(self, key):
        return self.d1.values()

    def itervalues(self, key):
        return self.d1.itervalues()


class UnauthorisedLogon(Exception):
    """ Exception to be raised when the user login fails
    due to incorrect user credentials.
    """
    pass

def ROSProxyClient(HOST, PORT, AUTHKEY):
    class DictManager(SyncManager):
        pass
    DictManager.register('get_dict')
    manager = DictManager(address = (HOST, PORT), authkey = AUTHKEY)
    manager.connect() # This starts the connected client
    return manager
    
def ROSProxyServer(HOST, PORT, AUTHKEY):
    Users = {}
    class DictManager(SyncManager):
        pass
    DictManager.register('get_dict', callable = lambda: Users)
    manager = DictManager(address = (HOST, PORT), authkey = AUTHKEY)
    manager.start() # This starts the connected client
    return manager

class ConsoleDummyRealm(object):
    implements(IRealm)
    
    def __init__(self, reactor, rce):
        self._reactor = reactor
        self._rce = rce
        
    def requestAvatar(self, avatarId, mind, *interfaces):
    
        if IPerspective not in interfaces:
            raise NotImplementedError('RoboEarthCloudEngine only '
                                      'handles IPerspective.')

        user = self._rce._getUser(avatarId)
        avatar = UserAvatar(user, self._rce._console)
        def detach():
            if sys.getrefcount(user) <= 4:
                print sys.getrefcount(user)
                user.destroy()
                del self._rce._users[avatarId]
        print('Connection from User.', sys.getrefcount(user))
        
        return IPerspective, avatar, detach

class UserAvatar(Avatar):
    def __init__(self, user, console):
        self.user = user
        self.console = console

    def perspective_list_machines(self):
        return defer.succeed(self.console._list_machines())
    
    def perspective_admin_add_user(self, username, password):
        self.console._root._checker.addUser(username, password)
   
    def perspective_start_container(self, tag):
        self.user.remote_createContainer(tag)
    
    def perspective_stop_container(self, tag):
        self.user.remote_destroyContainer(tag)
    
    def perspective_get_rosapi_connect_info(self, tag):
        uid = uuid4().hex
        try:
            self.user._containers[tag]._obj.registerconsole(self.user.userID, uid)
            d = self.user._containers[tag].getConnectInfo()
            d.addCallback(lambda addr: (addr, uid))
            return d
        except KeyError:
            raise InternalError('No such container')
            
    def perspective_start_node(self, cTag, nTag, pkg, exe, args):
        self.user.remote_addNode(cTag, nTag, pkg, exe, args)
    
    def perspective_stop_node(self, cTag, nTag):
        self.user.remote_removeNode(cTag, nTag)
        
    def perspective_add_parameter(self, cTag, name, value):
        self.user.remote_addParameter(cTag, name, value)
        
    def perspective_remove_parameter(self, cTag, name):
        self.user.remote_removeParameter(cTag, name)
        
    def perspective_add_interface(self, eTag, iTag, iType, iCls, addr = ''):
        self.user.remote_addInterface(eTag, iTag, iType, iCls, addr)

    def perspective_remove_interface(self, eTag, iTag):
        self.user.remote_removeInterface(eTag, iTag)
    
    def perspective_add_connection(self, tag1, tag2):
        self.user.remote_addConnection(tag1, tag2)    
        
    def perspective_remove_connection(self, tag1, tag2):
        self.user.remote_removeConnection(tag1, tag2)
    
    def perspective_start_robot(self, robotID):
        self.user.createRobot(robotID)
    
    def perspective_stop_robot(self, robotID):
        pass
    
    def perspective_list_robots(self):
        return defer.succeed(self.console._list_user_robots(self.user))

class Console(object):
    """
    The selective class that helps implement the console abilities
    """
    
    def __init__(self,root):
        """ Initialize the Console Handler.
            
            @param root:        Reference to top level of data structure.
            @type  root:        rce.master.core.RoboEarthCloudEngine
        """
        self._root = root
    
    
    # The following method is only accessible to the Admin user
    def _list_machines(self):
        """ Gets a list of all machines that are available in the Cloud Engine
        This should be only accessible to the top level admin for security reasons
        
        @return:            List of machines .
        @rtype:             List(rce.master.machine.Machine)
        """
        return self._root._balancer._machines
    
    def _list_machines_byIP(self):
        """ Gets a list of all machines that are available in the Cloud Engine
        This should be only accessible to the top level admin for security reasons
        
        @return:            List of machines by IPv4 addresses 
        @rtype:             List(str)
        """
        return [machine.IP for machine in self._list_machines()]
    
    def _list_machine_containers(self, machine):
        """ Gets a list of all containers available in the Machine
        This should be only accessible to the top level admin for security reasons
        
        @param machine:        Machine for which the containers need to be listed.
        @type  machine:        rce.master.machine.Machine
        
        @return:               List of containers .
        @rtype:                List(rce.master.container.Container)
        """
        return machine._containers

    def _list_machine_stats(self, machine):
        """ Gets some useful facts about the Machine
        This should be only accessible to the top level admin for security reasons
        
        @param machine:        Machine for which the containers need to be listed.
        @type  machine:        rce.master.machine.Machine
        
        @return:               List of containers .
        @rtype:                List(rce.master.container.Container)
        """
        stat_info = {'active': machine.active,
                     'IP' :  machine.IP,
                     'capacity' : machine.capacity}
        return stat_info
    
    def _list_machine_users(self, machine):
        """ Gets some useful facts about the Machine
        This should be only accessible to the top level admin for security reasons
        
        @param machine:        Machine for which the containers need to be listed.
        @type  machine:        rce.master.machine.Machine
        
        @return:               Counter containing the users and the number of containers they are running .
        @rtype:                List collections.Counter
        """
        return machine._users.keys()
    
    def _list_userID(self):
        """ Gets a list of all users that are logged into the Cloud Engine
        This should be only accessible to the top level admin for security reasons
        
        @return:            List of users .
        @rtype:             list(str)
        """
        return self._root._users.keys()

    def _admin_add_user(self, username, password):
        """ Add a user to the RoboEarth Cloud Engine

        @param username:         Username of the user to be added
        @type username:         str

        @param password:        Password of the user to be added
        @type  passowrd:        str

        @return:            Results to True if succeeded  .
        @rtype:             boolean
        """
        self._root._checker.addUser(username, password)

    def _admin_remove_user(self, username, password):
        """ Remove a user to the RoboEarth Cloud Engine

        @param username:         Username of the user to be removed
        @type username:         str

        @return:            Results to True if succeeded  .
        @rtype:             boolean
        """
        self._root._checker.removeUser(username)

    def _admin_user_passwd(self, username, password):
        """ Add a user to the RoboEarth Cloud Engine

        @param username:         Username of the user to be added
        @type username:         str

        @param password:        Password of the user to be added
        @type  passowrd:        str

        @return:            Results to True if succeeded  .
        @rtype:             boolean
        """
        self._root._checker.passwd(username, password)
    
    def _list_user_robots(self, user):
        """ Retrieve a list of all the robots owned by the user.
        
        @param user:         User logged into the cloud engine.
        @type:               rce.master.user.User
        
        @return:             List of Robot uuids of rce.master.user.Robot.
        @rtype:              list(str)
        """
        return user._robots.keys()
    
    def _list_user_containers(self, user):
        """ Retrieve a list of all the containers owned by the user.
        
        @param user:         User logged into the cloud engine.
        @type:               rce.master.user.User
        
        @return:             List of Container tags to rce.master.user.Container
        @rtype:              list(str) 
        """
        return user._containers.keys()
        
    def _list_user_connections(self, user):
        """ Retrieve a list of all the connections made by the user.
        
        @param user:         User logged into the cloud engine.
        @rtype:              rce.master.user.User
        
        @return:             List of hashed connection keys to rce.master.network.Connection
        @rtype:              list(str)
        """
        return user._connections.keys()
    
    def _retrieve_robot_byUUID(self, user, uuid):
        """Gets a Robot given the key and user
        
        @param user:         User logged into the cloud engine.
        @type:               rce.master.user.User
        
        @param uuid:         uuid assosicated to the robot object to be fetched
        @type:               str
        
        @return:             Robot object
        @rtype:              rce.master.user.Robot 
        
        """
        return user._robots.get(uuid)
    
    def _retrieve_container_byTag(self, user, tag):
        """Gets a User given the usedID
        
        @param user:             User logged into the cloud engine.
        @type:                   rce.master.user.User
        
        @param uuid:             tag assosicated to the container object to be fetched
        @type:                   str
        
        @return:                 Container object
        @rtype:                  rce.master.user.Container
        
        """
        return user._containers.get(tag)
    
    def _retrieve_connection_byHash(self, user, hash_key):
        """Gets a User given the usedID
        
        @param user:             User logged into the cloud engine.
        @type:                   rce.master.user.User
        
        @param uuid:             hash_key assosicated to the connection object to be fetched
        @type:                   str
        
        @return:                 Container object
        @rtype:                  rce.master.user.Container
        
        """
        return user._connection.get(hash_key)


    # TODO : Please read
    # The above functions expose a bunch of basic objects form the cloud engine , the rest of these methods use the exposed objects in convenient wrappers ,
    # feel free to edit and modify these as required alternatively one could use the above to generate the required behavior.

    def generate_user_graph(self, user):
        """Generates a multidict representation of the users connect graph across the cloud engine.
        Useful for visualizing and debugging a users activities and connections.
        """
        #build the physical container graph
        def get_containmer_tree(tag):
            container = self._retrieve_container_byTag(user, tag)
            nodes = container._nodes.keys()
            parameters = container._parameters.keys()
            interfaces = container._interfaces.keys()
            return {tag:{'nodes':nodes,'parameters':parameters,
                         'interfaces':interfaces}}

        machines = defaultdict(list)
        for tag,container in user._containers.iteritems():
            machines[container._machine.IP].append(get_containmer_tree(tag))

        #build the robots graph
        robots = {}
        for uuid,robot in user._robots.iteritems():
            robots[uuid] =  robot._interfaces.keys()
        # build the connections map
        connections = InterfaceConnection2way()
        for connection in user._connections.itervalues():
            connections[connection._connectionA._interface._uid] = \
                                 connection._connectionB._interface._uid

        return {'userID':user._userID,'network':machines,
                'robots':robots, 'connections': connections}
