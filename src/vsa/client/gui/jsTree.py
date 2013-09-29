# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2013 Mellanox Technologies, Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import copy

class jsTree(object):
    def __init__(self, id="", title="", icon="", imagesLocation=None):
        """
        The description of __init__ comes here.
        @param id
        @param title
        @param icon
        @param imagesLocation
        @return
        """
        self.images = imagesLocation
        if not self.images:
            self.images="/vsa_static/icons-vsa/"

        nid = self._normelize_id(id)
        self.tree = {
            "attr": {
                "id": nid
            },
            "data": {
                "title": str(title),
                "icon": ""
            },
            "metadata": {
                "path": str(id)
            },
            "children": []
        }

        if icon!="":
            self.Icon=icon

    def __getId(self):
        """
        The description of __getId comes here.
        @return
        """
        return self.tree["attr"]["id"]

    def __setId(self, value):
        """
        The description of __setId comes here.
        @param value
        @return
        """
        self.tree["attr"]["id"]=str(value)

    Id = property(__getId, __setId)

    def __getTitle(self):
        """
        The description of __getTitle comes here.
        @return
        """
        return self.tree["data"]["title"]

    def __setTitle(self, value):
        """
        The description of __setTitle comes here.
        @param value
        @return
        """
        self.tree["data"]["title"]=str(value)

    Title = property(__getTitle, __setTitle)

    def __getIcon(self):
        """
        The description of __getIcon comes here.
        @return
        """
        return self.tree["data"]["icon"]

    def __setIcon(self, value):
        """
        The description of __setIcon comes here.
        @param value
        @return
        """
        if value!="":
            value=self.images+str(value)
        self.tree["data"]["icon"]=str(value)

    Icon = property(__getIcon, __setIcon)

    def _normelize_id(self, id):
        """
        The description of _normelize_id comes here.
        @param id
        @return
        """
        replaced_chars = ['/', '!', '.',':','\\']
        id = id.lstrip(''.join(replaced_chars))
        id = reduce(lambda id, rc: id.replace(rc, '_'), replaced_chars, id)
        return str(id)

    def AddChild(self, id="", title="", icon=""):
        """
        The description of AddChild comes here.
        @param id
        @param title
        @param icon
        @return
        """
        n=jsTree(id, title, icon)
        self.tree["children"].append(n)
        return n

    @property
    def Childs(self):
        """get list of child nodes"""
        return self.tree["children"]

    def GetTree(self):
        """recursive generation of tree dictionary"""
        n=copy.copy(self.tree)
        n["children"]=[]
        for c in self.Childs:
            n["children"].append(c.GetTree())
        return n

    def FindChild(self, id):
        """find child node based id"""
        for c in self.Childs:
            if id==c.Id:
                return c
        return None

def BuildDefaultTree():
    """build default tree for VSA and return its root"""
    root=jsTree()
    n=root.AddChild("physical/disks", "Physical disks");
    n.AddChild("physical.disks.1", "Disk 1", "drive.jpg");
    n=root.AddChild("targets", "Targets");
    t=n.AddChild("targets.1", "Target 1", "target.jpg");
    t.AddChild("targets.1.lun1", "Lun 1", "lun.jpg");
    n=root.AddChild("groups", "Server groups");
    n.AddChild("groups.everyone", "Everyone", "acl.jpg");
    return root


##print BuildDefaultTree().GetTree()
