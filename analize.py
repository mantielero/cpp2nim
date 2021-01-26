#!/usr/bin/env python
""" Usage: call with <filename> <typename>
python cpp2nim.py "/usr/include/opencascade/gp_*.hxx" occt
python cpp2nim.py /usr/include/osg/Geode geode

python cpp2nim.py "/usr/include/osg/**/*" osg
python cpp2nim.py "/usr/include/osgViewer/**/*" osgViewer
>>> import clang.cindex
>>> index = clang.cindex.Index.create()
>>> tu = index.parse("/usr/include/opencascade/gp_Pnt.hxx", ['-x', 'c++',  "-I/usr/include/opencascade"], None, clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD)

clang -Xclang -ast-dump=json -x c++ -I/usr/include/osg -fsyntax-only /usr/include/osg/Geode  > geode.json

clang -Xclang -ast-dump -fno-diagnostics-color miniz.c
c2nim --cpp --header --out:gp_Pnt.nim /usr/include/opencascade/gp_Pnt.hxx

clang -Xclang -ast-dump -x c++ -I /usr/include/osg ./osg.hpp -fsyntax-only > osg.ast

https://github.com/StatisKit/AutoWIG/blob/master/src/py/autowig/libclang_parser.py
-----
TODO: https://forum.nim-lang.org/t/7324

/home/jose/src/3d/osg/osg/Geometry.nim(26, 62) Error: type mismatch: got <Options> but expected 'CopyOp = object'

proc constructGeometry*(geometry: Geometry, copyop: CopyOp = SHALLOW_COPY): Geometry {.constructor,importcpp: "osg::Geometry::Geometry(@)".}

the solution is to do:

1. Replacing:
$ sed -i 's/CopyOp = SHALLOW_COPY/CopyOp = constructCopyOp(CopyFlags(SHALLOW_COPY))/g' *

2. Adding:
from CopyOp import constructCopyOp,CopyFlags

----
TODO: "value_type" debería ser "Value_type"


----
TODO: VectorGLuint se define en PrimitiveSet y lo pide PrimitiveSetIndirect
(Línea 49)

---
TODO:  PrimitiveSetIndirect línea 74
En el mismo fichero:
proc constructDrawElementsIndirect*(primType: psType, mode: GLenum = 0
 Error: type mismatch: got <int literal(0)> but expected 'GLenum = distinct uint32'
 (creo que debería usar nil)


-----
TODO: operators
proc `[]=`[K, V](this: var StdMap[K, V]; key: K; val: V) {.
  importcpp: "#[#] = #", header: "<map>".}

-----
TODO: to check the Array file: python cpp2nim3.py "/usr/include/osg/Array" borrame

-----
TODO: si sale Clase & significa que hay que usar byref y en caso contrario: bycopy
-----
TODO: for some reason, the enum gets repited:
    tpInt64ArrayType = 37,
    tpLastArrayType = 37,

It needs to be replaced by something like:
   let tpLastArrayType:Type = tpInt64ArrayType

C++ allows using the same ID for different ID
-----
TODO: https://nim-lang.org/docs/tut2.html#object-oriented-programming-inheritance
Definición de tipos. Si usamos "object of <something>", en algún momento 
habrá que hacer un "object of RootObj". También hay que tener claro si usamos:
"ref object of RootObj"

----
TODO: /usr/include/osg/Referenced
proc constructdepends_on*[T, M](): depends_on {.constructor,importcpp: "depends_on<T, M>".}

----
TODO: probably, inlines, shouldn't be included. The same applies to private and protected!

-----
TODO: functions
"""

import sys
import clang.cindex
import string
import os
import glob
import textwrap
import re
from pprint import pprint
from pathlib import Path
import collections
from export import *



def _relationships( data, provides, missing ):
    """For each file it gives the files providing some dependencies
    (a set of dependencies)
    """
    _new = {}
    _filenames = set([_tmp[0] for _tmp in data])

    for file in _filenames:
        _missing = missing[file]
        _data = {}
        for f in _filenames:
            if f != file:
                # The normal case
                _provides = provides[f] 
                _found = _missing.intersection(_provides)
                if len(_found) > 0:
                    _data[f] = _found

                # The enum case
                _tmp = [k[0] for k in _provides if type(k) is tuple]
                _found2 = _missing.intersection(_tmp)
                
                _enumFound = []
                if len(_found2) > 0:
                    for item in _found2:
                        for k in _provides:
                            if type(k) is tuple:
                                if item == k[0]:
                                    _enumFound.append( k[1])
                _enumFound = list(set(_enumFound))
                if len(_found) > 0 or len(_enumFound) > 0:
                    _data[f] = set(list(_found) + _enumFound)

        _new[file] = _data
    return _new

def find_dependencies(obj, data):
    _newImports = set([])
    _deps = set([])
    for i in range(len(data)):
        if data[i][2] in ["typedef", "class"]:
            _values = data[i][4]

            if "RefMatrix" in obj and data[i][2] == "typedef":
                #if "osg::RefMatrix" in _values["fully_qualified"]:
                    print(obj)
                    pprint(_values)            
            if _values["fully_qualified"] == obj:

                # If the type depend on other types, they need to be moved too.
                # - For instance a typedef might have an underlying dep
                if "underlying_deps" in _values:
                    # Search for classes with the same fully qualified identifier
                    _idx = [j for j in range(len(data)) if data[j][2] == "class"]
                    _classesFully = [data[j][4]["fully_qualified"] for j in _idx]
                    _classes = [data[j][3] for j in _idx]     
                    
                    #if len(_values["underlying_deps"]) == 0:


                    for _i in _values["underlying_deps"]:
                        # If found, move it
                     
                        if _i in _classesFully:
                            if not _i in _deps:
                                _newdeps = find_dependencies(_i, data)                                
                                _deps.add(_i)
                                _deps = _deps.union(_newdeps)

                                #find_dependencies
                            #_k = _classesFully.index(_i)
                            #_k = _idx[_k]
                            #_newImports.add(data[i][0])

                            #data[_k] = tuple( [newfilename] + list(data[_k][1:]) )

                        elif _i in _classes:                          
                            _k = _classes.index(_i)
                            _k = _idx[_k]
                            #print(_i)
                            #print(data[_k][4]["fully_qualified"])
                            _fullname = data[_k][4]["fully_qualified"]                          
                            _newdeps = find_dependencies(_fullname, data)                                
                            _deps.add(_fullname)
                            _deps = _deps.union(_newdeps)                                                     
                        #    _newImports.add(data[i][0])
                        #    data[_k] = tuple( [newfilename] + list(data[_k][1:]) ) 

                # - Also when a template is used, we check its params
              
                if "template_params" in _values:
                    if len(_values["template_params"]) > 0:
                        # Search for enums that might be used in the params
                        _idx = [j for j in range(len(data)) if data[j][2] in ["enum"]]
                        _fullyEnum = [data[j][3] for j in _idx]
                       
                        for template_param in _values["template_params"]:
                            if type(template_param) == tuple:
                                for k in range(len(_fullyEnum)):
                                    _enumType = _fullyEnum[k]
                                    if _enumType.endswith( template_param[1] ) and "::" in template_param[1]:
                                        if not _enumType in _deps:
                                            _newdeps = find_dependencies(_enumType, data)                                               
                                            _deps.add(_enumType)                                        
                                            _deps = _deps.union(_newdeps)                                              
                                        #_deps.add(_enumType)
                                        #_k = _idx[k]
                                        #_newImports.add(data[i][0])
                                        #data[_k] = tuple( [newfilename] + list(data[_k][1:]) )     
    return _deps

def move_to_shared_types( newfilename, data,  _root, relations = {} ):
    # Dictionary with the files that are providing objects to other files
    """
    _providers = {}
    for _, _dict in _relations.items():
        for k, sets in _dict.items():
            # Acumulate all the sets associate to a specific file.
            _set = _providers.get(k, set([]))
            _set = _set.union(sets)
            _providers[k] = _set
    """
    # Objects that need to be moved
    _objects = set([])
    for _, _dict in _relations.items():
        for _, sets in _dict.items():
            # Acumulate all the sets associate to a specific file.
            _objects = _objects.union(sets)  

    # Add dependencies to te list
    _all = set(_objects)
    #for i in _all:
    #    if "Template" in i:
    #        print(i)
    #pprint(_all)
    for obj in _objects:
        _tmp = find_dependencies(obj, data)
        _all = _all.union(_tmp)

    # Move items to the new file
    _newImports = set([])
    for obj in _all:
        for i in range(len(data)):
            _tmp = data[i]        
            _file = _tmp[1]
            _type = _tmp[2]

            # Check the consts
            if _type == "const":
                _values = _tmp[3]
                for item in _values["items"]:
                    if item["name"] == obj:
                        _newImports.add( data[i][0] )
                        data[i] = tuple( [newfilename] + list( data[i][1:] ) )

            # Check the enums
            elif _type == "enum":
                _name = _tmp[3]
                _values = _tmp[4]
                if _name == obj:
                    #if _name not in _avoid: # The repeated identifiers are avoided
                    _newImports.add(data[i][0])
                    data[i] = tuple( [newfilename] + list(data[i][1:]) )
                    #else:
                    #    pass # Si el enum está en avoided habría que importarlo de algún sitio

            # Check the other types
            elif _type in  ["typedef", "class", "struct"]:
                _name = _tmp[3]
                _values = _tmp[4]                

                # If the following is met, we need to move it to the shared types file
                if _values["fully_qualified"] == obj:      
                    _newImports.add(data[i][0])                    
                    data[i] = tuple( [newfilename] + list(data[i][1:]) )
                    """
                    # If the type depend on other types, they need to be moved too.
                    # - For instance a typedef might have an underlying dep
                    if "underlying_deps" in _values:
                        # Search for classes with the same fully qualified identifier
                        _idx = [j for j in range(len(data)) if data[j][2] == "class"]
                        _classesFully = [data[j][4]["fully_qualified"] for j in _idx]
                        _classes = [data[j][3] for j in _idx]     
                                          
                        for _i in _values["underlying_deps"]:
                            # If found, move it
                            if _i in _classesFully:
                                _k = _classesFully.index(_i)
                                _k = _idx[_k]
                                _newImports.add(data[i][0])
                                data[_k] = tuple( [newfilename] + list(data[_k][1:]) )

                            elif _i in _classes:
                                _k = _classes.index(_i)
                                _k = _idx[_k]
                                _newImports.add(data[i][0])
                                data[_k] = tuple( [newfilename] + list(data[_k][1:]) ) 

                    # - Also when a template is used, we check its params
                    if "template_params" in _values:
                        if len(_values["template_params"]) > 0:
                            # Search for enums that might be used in the params
                            _idx = [j for j in range(len(data)) if data[j][2] in ["enum"]]
                            _fullyEnum = [data[j][3] for j in _idx]
                            
                            for template_param in _values["template_params"]:
                                if type(template_param) == tuple:
                                    for k in range(len(_fullyEnum)):
                                        _enumType = _fullyEnum[k]
                                        if _enumType.endswith( template_param[1] ) and "::" in template_param[1]:
                                            _k = _idx[k]
                                            _newImports.add(data[i][0])
                                            data[_k] = tuple( [newfilename] + list(data[_k][1:]) ) 
                    """               
                        

    # Add the new imports
    _new = []
    for i in _newImports:
        _new.append( (i, None, "import", [newfilename]) )
    return _new + data




"""
def _get_objects_provided_per_file( data, _relations ):
    ""This creates a dictionary with all the objects provided by each file and
    that are needed by some other file.

    Creates a dictionary with the identifiers provided by each file.

    It provides: file -> set where the set contains the fully_qualified.
    '/usr/include/osg/ValueMap':    {'osg::ValueMap'},
    '/usr/include/osg/ValueObject': {'osg::TemplateValueObject',
                                     'osg::ValueObject'},
    '/usr/include/osg/ValueStack':  {'osg::ValueStack'},
    '/usr/include/osg/Vec2':        {'osg::Vec2'},

    ""
    _filter = {}
    #_pf = [i for i in data if len(i) == 4]  # Filter data
    for _, _dict in _relations.items():
        for k, sets in _dict.items():
            # Acumulate all the sets associate to a specific file.
            _set = _filter.get(k, set([]))
            _set = _set.union(sets)

            


            # Relates the enum's items with the corresponding identifier
            # This provides some like: {"myId1" : "namespace::myEnumType", ...}
            _pfEnums = {}
            _enums = [_tmp for _tmp in data if _tmp[0] == k and _tmp[1] == "enum"]
            for _,_,enumType,_values in _enums:
                for enum in _values["items"]:
                    _pfEnums[enum["name"]] = enumType
            
            
            _td = [_tmp for _tmp in data if _tmp[0] == k and _tmp[1] == "typedef"] # Typedefs for the file
            _classes = [(_tmp[2],_tmp[3]["fully_qualified"]) for _tmp in data if _tmp[0] == k and _tmp[1] == "class"]
            _classes = dict(_classes)
            for _filename, _type, _key, value in _td: # Iterate on them
                if "underlying_deps" in value:  # For those having this field
                    for _i in value["underlying_deps"]:  # Iterate on their items
                        if _i in _classes:      
                            _set.add(_classes[_i]) #shared["class"].append( get_class(_i,_v, _fname) )
                        for _j, key2 in _pfEnums.items():
                            if _j.endswith(_i):
                                _set.add( key2) 
                #_aa = list(value.keys())
                #for _i in _aa:
                #    if "template" in _i:
                #        print(_i)
                #if "template_params" in value:
                #    for _i in value["template_params"]:
                #        pprint(_i)


            _filter[k] = _set
    return _filter   
"""
"""
def _get_repeated_identifiers(_filter):
    ""They will need to go in different files.
    {'Type': [('/usr/include/osg/StateAttribute', 'osg::StateAttribute::Type'),
              ('/usr/include/osg/Uniform', 'osg::Uniform::Type'),
              ('/usr/include/osg/PrimitiveSet', 'osg::PrimitiveSet::Type')]}
    ""    
    _identifiers = [_item.split("::")[-1] for _file, _set in _filter.items() for _item in _set]
    _repeatedNames = set([x for x in _identifiers if _identifiers.count(x) > 1])
    _repeated = {}
    for i in _repeatedNames:
        _list = _repeated.get(i,[])
        for k,v in _filter.items():
            for item in v:
                if item.split("::")[-1] == i:
                    _list.append((k,item))
        _repeated[i] = _list
    return _repeated

# TODO: en lo siguiente, renombrar Type a PrimitiveSet.Type, por ejemplo
"""

def _get_renames_identifiers(newfilename, data):
    """They will need to go in different files.
    {'Type': [('/usr/include/osg/StateAttribute', 'osg::StateAttribute::Type'),
              ('/usr/include/osg/Uniform', 'osg::Uniform::Type'),
              ('/usr/include/osg/PrimitiveSet', 'osg::PrimitiveSet::Type')]}
    """
    idx = [i for i in range(len(data)) if data[i][0] == newfilename]
    enums = [(i, data[i][3],data[i][3].split("::")[-1]) for i in idx if data[i][2] == "enum"]
    #pprint(enums)
    #classes = [(i,data[i][4]["fully_qualified"], data[i][4]["fully_qualified"].split("::")[-1]) for i in idx if data[i][2] == "class"]    
    objects = [(i,data[i][4]["fully_qualified"], data[i][4]["fully_qualified"].split("::")[-1]) for i in idx if data[i][2] in ["class","typedef"]]     
    _list = enums + objects
    names = [name for _,_,name in _list]
    repeated_names = set( [name for name in names if names.count(name) > 1] )

    _renamer = {}

    #for name in repeated_names:
    for i, _fully, _name  in _list:
        if _name in repeated_names:
            _newname = get_new_name(_fully, list(_renamer.values()) )
            _renamer.update( {_fully : _newname} )

    return _renamer

"""
def send_to_shared_types_old( data, _filter, _root, _repeated, newfilename ):
    # These are avoided because they have the same identifier in on file.
    _avoid = set([])
    _avoidDict = {}
    for k, values in _repeated.items():
        for f,v in values:
            _avoid.add(v)
            _tmp = os.path.basename(f)
            _avoidDict[v] = _tmp

    _newImports = set([])
    for file, objects in _filter.items():
        for i in range(len(data)):
            _tmp = data[i]        
            _file = _tmp[1]
            _type = _tmp[2]

            if _type == "const":
                _values = _tmp[3]
                for item in _values["items"]:
                    if item["name"] in objects:
                        _newImports.add(data[i][0])
                        data[i] = tuple( [newfilename] + list(data[i][1:]) )

            elif _type == "enum":
                _name = _tmp[3]
                _values = _tmp[4]
                if _name in objects:
                    if _name not in _avoid: # The repeated identifiers are avoided
                        _newImports.add(data[i][0])
                        data[i] = tuple( [newfilename] + list(data[i][1:]) )
                    else:
                        pass # Si el enum está en avoided habría que importarlo de algún sitio

            elif _type in  ["typedef", "class", "struct"]:
                _name = _tmp[3]
                _values = _tmp[4]                

                if _values["fully_qualified"] in objects and _values["fully_qualified"] not in _avoid:
                  
                    _newImports.add(data[i][0])                    
                    data[i] = tuple( [newfilename] + list(data[i][1:]) )

                    if "underlying_deps" in _values:
                        _idx = [j for j in range(len(data)) if data[j][2] == "class"]
                        _classesFully = [data[j][4]["fully_qualified"] for j in _idx]
                        _classes = [data[j][3] for j in _idx]     
                                          
                        for _i in _values["underlying_deps"]:
                            if _i in _classesFully:
                                _k = _classesFully.index(_i)
                                _k = _idx[_k]
                                _newImports.add(data[i][0])
                                data[_k] = tuple( [newfilename] + list(data[_k][1:]) )

                            elif _i in _classes:
                                _k = _classes.index(_i)
                                _k = _idx[_k]
                                _newImports.add(data[i][0])
                                data[_k] = tuple( [newfilename] + list(data[_k][1:]) ) 

                    if "template_params" in _values:
                        if len(_values["template_params"]) > 0:
                            #pprint(_values["template_params"])
                            _idx = [j for j in range(len(data)) if data[j][2] in ["enum"]]
                            _fullyEnum = [data[j][3] for j in _idx]
                            #pprint(_fullyEnum)
                            
                            #_templateTypes = set([])
                            for template_param in _values["template_params"]:
                                if type(template_param) == tuple:
                                    #print(i[1])
                                    for k in range(len(_fullyEnum)):
                                        _enumType = _fullyEnum[k]
                                        if _enumType.endswith( template_param[1] ) and "::" in template_param[1]:
                                            #_k = _fullyEnum.index(k)
                                            _k = _idx[k]
                                            _newImports.add(data[i][0])
                                            data[_k] = tuple( [newfilename] + list(data[_k][1:]) ) 
                                   
                        


    _new = []
    for i in _newImports:
        _new.append( (i, None, "import", [newfilename]) )
    #pprint(_new)
    return _new + data
"""

def get_root(data):
    n  = 1000000000000000000000
    filenames = set([i[0] for i in data])
    for file in filenames:
        _tmp = os.path.split(file)[0]
        n = min(n, len(_tmp))
    return file[0:n]

def get_new_name(_full, names):
    _tmp = _full.split("::")
    # Option 1: upper case letters
    res = [char.lower() for char in _tmp[-2] if char.isupper()] 
    res = f"{''.join(res)}{_tmp[-1]}"
    if res not in names:
        return res

    # Option 2:
    for i in range(len(_tmp[-2])):
        if f"{_tmp[-2][0:i+1]}{_tmp[-1]}" not in names:
            return f"{_tmp[-2][0:i+1]}{_tmp[-1]}"

    # Option 3:
    _letters = "abcefghijklmnopqrstuvwxyz"
    for i in range(len(_letters)):
        for j in range(len(_letters)):
            for k in range(len(_letters)):
                val = f"{_letters[i]}{_letters[j]}{_letters[k]}{_tmp[-1]}"
                if val not in names:
                    return _val


#==============================================================
if __name__ == '__main__':
    import pickle
    # Read the command line: it takes a glob and a destination
    _dest = sys.argv[1]
    _path = os.getcwd()
    _destination_folder = os.path.join(_path, _dest)
    _delete_folder = os.path.join(_dest, "deleteme")    


    _files_name = os.path.join(_delete_folder, 'files.pickle')
    fp = open(_files_name, 'rb')
    _tmp = pickle.load(fp)
    data      = _tmp["includes"]
    dependsOn = _tmp["dependsOn"]
    provides  = _tmp["provides"]
    missing   = _tmp["missing"]            
    fp.close()

    _relations = _relationships( data , provides, missing)
    #_filter    = _get_objects_provided_per_file( data, _relations )
    #pprint(_filter)
    #_repeated  = _get_repeated_identifiers( _filter )
    #pprint(_repeated)



    #
    #pprint(_filter["/usr/include/osg/Array"])
    #pprint(dependsOn["/usr/include/osg/Array"])

    # Add a column to indicate where the values will be stored
    _root = get_root(data)
    _new = []
    for i in data:
        _tmp = os.path.splitext(i[0])[0]
        _destFilename = os.path.relpath(_tmp, _root)
        _destFilename += ".nim"
        _tmp = tuple( [_destFilename] + list(i))
        _new.append( _tmp )
    data = _new

    # Aquello que es compartido por varios ficheros se lleva al raiz
    _newfilename = os.path.join( f"{_dest}_types.nim" )

    # Move those definitions which are shared (in filter) to "osg_types.nim"
    data = move_to_shared_types( _newfilename, data,  _root, relations = _relations)
    #data = send_to_shared_types( data,  _filter, _root, _repeated, _newfilename ) 

    # Check the data that it is now in {dest}_types (the shared file) 
    _tmpNames = set([])
    _tmpFully = set([])
    for i in data:
        if i[0].endswith( f"{_dest}_types.nim" ):
            _name = i[3]
            _fully = None
            if len(i)  > 4:
                if "fully_qualified" in i[4]:
                    _fully = i[4]["fully_qualified"]
            if type(_name) != list:
                _tmpNames.add( _name )
            _tmpFully.add( _fully )
    _tmp = []
    _done = []
    for i in range(len(data)):
        if not data[i][0].endswith( f"{_dest}_types.nim" ) and data[i][0] not in _done:
            _done.append( data[i][0] )
            _tmp.append( (data[i][0], None, "import",[f"{_dest}_types"]) )
    data = _tmp + data

    # Avoid module importing itself
    _deleteme = []
    for i in range(len(data)):
        _file = os.path.basename(data[i][0])
        _type = data[i][2]
        if _type == "import":
            if _file in data[i][3]:
                _deleteme.append( i )
    for i in _deleteme[::-1]:
        data.pop( i )

    # Avoid importing twice the same module
    _deleteme = [ i for i in range(len(data)) if data[i][2] == "import"]
    _dict = {}
    for _tmp in data:
        if _tmp[2] == "import":
            _val = _dict.get( _tmp[0], set([]) )
            _list = [os.path.splitext(i)[0] for i in _tmp[3]]
            _val = _val.union( set(_list ) )
            _dict[_tmp[0]] = _val
    for i in _deleteme[::-1]:
        data.pop( i )
    
    _tmp = []
    for _file,_set  in _dict.items():
        for i in _set:
        #if not data[i][0].endswith( f"{_dest}_types.nim" ) and data[i][0] not in _done:
            #_done.append( data[i][0] )
            _tmp.append( (_file, None, "import",[i]) )
    data = _tmp + data    


        #_tmp2 = _tmp1.get(_file, {"idx": [], ""})
        #_tmp2.append(i, _list)



    # TODO: it is still missing checking all the enums.

    #for k, values in dependsOn.items():
    #    print(values)
    print("\n\n\n")
    #pprint(dependsOn["/usr/include/osg/AnimationPath"])


    # ROOT FILE
    _destFiles = set( [i[0] for i in data] ) 

    _pragma = '{.passL: "-losg -losgSim -losgAnimation -losgTerrain -losgDB -losgText -losgFX -losgUI -losgGA -losgUtil -losgManipulator -losgViewer -losgParticle -losgVolume -losgPresentation -losgWidget -losgShadow", passC:"-I/usr/include/osg" .}\n\n'
    data = [(f"{_dest}.nim", None, "pragma", None, _pragma )] + data
    
    for _file in _destFiles:
        _fname = os.path.splitext(_file)[0]
        if _fname != f"{_dest}_types":
            data = [(f"{_dest}.nim", None, "import", [_fname])] + data             

    # Renaming
    rename = _get_renames_identifiers(_newfilename, data)
    #for _type, _list in _repeated.items():
    #    for _file, _full in _list:
    #        _v = get_new_name(_full, list(rename.values()))
    #        rename.update({_full: _v})
 
    #=========================
    # EXPORTING TO FILES
    #=========================
    _destFiles = set( [i[0] for i in data] )
    for destFile in _destFiles:
        _txt = export_txt( destFile, data, root = _root, rename=rename)        
            
        _fname = os.path.join(_destination_folder , destFile)        
        _fp = open(_fname, "w")
        _fp.write( _txt )
        _fp.close()
        #print("[INFO] Written: ", _fname)

    #-------------------------
    """
    # Encontramos quién depende de los comunes
    _dependants = {}
    for key, _list in _repeated.items():
        for _file, _object in _list:
            _dependants[_object] = set([])
            # Buscamos en las dependenias
            #if _file in _filter:    
            for _f,_values in _relations.items():
                for _provider, _set in _values.items():
                    if _provider == _file:
                        if _object in _set:
                            _dependants[_object].add( _f )
    """
