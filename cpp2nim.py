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

-----
TODO: si sale Clase & significa que hay que usar byref y en caso contrario: bycopy

------
TODO: MixinVector
To handle properly the templates.
 CursorKind.TRANSLATION_UNIT t.cpp
  CursorKind.CLASS_TEMPLATE X
   CursorKind.TEMPLATE_TYPE_PARAMETER T
  CursorKind.VAR_DECL x
   CursorKind.TEMPLATE_REF X
   CursorKind.CALL_EXPR X
1 x CursorKind.VAR_DECL TypeKind.INVALID
1 X CursorKind.CALL_EXPR TypeKind.INVALID
-----
TODO:
C2NIM:
importcpp: "osg::Geode(@)"
YO:
Geode(@)

-----
TODO: https://nim-lang.org/docs/tut2.html#object-oriented-programming-inheritance
Definición de tipos. Si usamos "object of <something>", en algún momento 
habrá que hacer un "object of RootObj". También hay que tener claro si usamos:
"ref object of RootObj"
----
TODO: 
type
  KeyValueMap* {.header: "ValueMap", importcpp: "KeyValueMap".} = cint
  UserValueObject* {.header: "ValueMap", importcpp: "UserValueObject".} = TemplateValueObject[T]
  UserValueObject* {.header: "ValueMap", importcpp: "UserValueObject".} = TemplateValueObject[T]
  UserValueObject* {.header: "ValueMap", importcpp: "UserValueObject".} = TemplateValueObject[T]
  value_type* {.header: "Vec4us", importcpp: "value_type".} = cushort
----
TODO: /usr/include/osg/Referenced
proc constructdepends_on*[T, M](): depends_on {.constructor,importcpp: "depends_on<T, M>".}

----
TODO: right order in enums
----
TODO: to add first the templates! For example the following:
  ByteArray* {.importcpp: "ByteArray".} = Templateindexarray[GLbyte,Bytearraytype,1,5120]
requires: Templateindexarray to be available beforehand
----
TODO: probably, inlines, shouldn't be included. The same applies to private and protected!
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
#from yaml import load, dump
#from yaml import CLoader as Loader, CDumper as Dumper
#import networkx as nx

def print_line(node, field, spc, ident= 0):
    try:
        param = getattr(node, field)
        if callable(param):
            param = param()
        print(f"{spc}{field}: {param}")
        if isinstance( param, clang.cindex.Cursor):
            pp(_tmp, ident+ 4)
        elif isinstance(param, clang.cindex.Type):
            pptype(param, ident+4)

        elif hasattr(param,'__iter__'):#isinstance(param, collections.Iterable):
            pass
              
    except:
        #print(f"{spc}{field}:  raises an exception!")    
        pass

def pptype(t, ident = 0):
    spc = " " * ident
    print(f"{spc}kind: ", node.kind) 
    print(f"{spc}spelling: ", node.spelling)    
    for i in dir(t):
        if not i.startswith("_") and i not in ["kind", "spelling"]:
            print_line(node, i, spc, ident)

def pp(node, ident = 0):
    """Pretty printer to inspect the nodes"""
    spc = " " * ident
    if ident == 0:
        print("======= TOP =======")
    else:
        print(f"{spc}------")
    print(f"{spc}kind: {node.kind}") 
    print(f"{spc}spelling: {node.spelling}" )
    for i in dir(node):
        if i not in ["kind", "spelling"] and not i.startswith("_"):
            print_line(node, i, spc, ident)   
    if ident == 0:
        print("======= BOTTOM =======")    
    else:
        print(f"{spc}------")

def get_nim_type( c_type ):   
    c_type = c_type.strip()

    isVar = True
    if c_type[0:5] == "const":
        c_type = c_type[5:].strip()
        isVar = False

    if c_type[-1] != "&":
        isVar = False
    else:
        c_type = c_type[:-1]

    c_type = c_type.strip()

    if c_type in ["void *"]:
        return "pointer"
    if c_type in ["long"]:
        return "clong"
    if c_type in ["unsigned long"]:
        return "culong"
    if c_type in ["short"]:
        return "cshort"
    if c_type in ["int"]:
        return "cint"
    if c_type in ["size_t"]:
        return "csize_t"    
    if c_type in ["long long"]:
        return "clonglong"              
    #if c_type in ["signed", "unsigned"]:
    #    return "cint"
    if c_type in ["long double"]:
        return "clongdouble" 
    if c_type in ["float"]:
        return "cfloat"        
    if c_type in ["double"]:
        return "cdouble"
    if c_type in ["char *"]:
        return "cstring"
    if c_type in ["char"]:
        return "cchar"
    if c_type in ["signed char"]:
        return "cschar"
    if c_type in ["unsigned char"]:
        return "cuchar"
    if c_type in ["unsigned short"]:
        return "cushort"
    if c_type in ["unsigned int"]:
        return "cuint"
    if c_type in ["unsigned long long"]:
        return "culonglong"
    if c_type in ["char**"]:
        return "cstringArray"

    if isVar:
        c_type = f"var {c_type}"

    # xxxx::yyyy<zzzzz> TODO: MODIFY <map>, [K]
    if "::" in c_type:
        kernel = re.compile("([^<]+)[<]*([^>]*)[>]*")
        _a, _b = kernel.findall(c_type)[0]
        _tmp = _a.split("::")[-1]
        _tmp = _tmp.capitalize()

        #my_dict["type"][_tmp] = "#" + f'{_tmp}* {{.importcpp: "{_a}", header: "<map>".}} [K] = object'
        if _tmp[-1] == "*":
            _tmp = f"ptr {_tmp[:-1]}"
        
        if _b != "":
            # There may be several types
            _b = _b.split(", ")
            _b = [get_nim_type(_i) for _i in _b]
            for idx in range(len(_b)):
                if _b[idx][-1] == "*":
                    _b[idx]  = f"ptr {_b[idx][:-1].strip()}"
            _b = ",".join(_b)
            _b = f"[{_b}]"
        return f"{_tmp}{_b}"

    if "<" in c_type and ">" in c_type:
        c_type = c_type.replace("<", "[")
        c_type = c_type.replace(">", "]")

    if c_type[-1] == "*":
        c_type = f"ptr {c_type[:-1].strip()}"
    return c_type


NIM_KEYWORDS = ["addr", "and", "as", "asm", "bind", "block", "break",
                "case", "cast", "concept", "const", "continue", "converter",
                "defer", "discard", "distinct", "div", "do", "elif", "else",
                "end", "enum", "except", "export", "finally", "for", "from",
                "func", "if", "import", "in", "include", "interface", "is",
                "isnot", "iterator", "let", "macro", "method", "mixin", "mod",
                "nil", "not", "notin", "object", "of", "or", "out", "proc", "ptr",
                "raise", "ref", "return", "shl", "shr", "static", "template",
                "try", "tuple", "type", "using", "var", "when", "while", "xor",
                "yield"]

def clean(txt):
    txt = txt.replace("const", "")
    txt = txt.strip()
    if txt[-2:] == " &":
        txt = txt[:-2]
    if txt[0] == "_":
        txt = "prefix" + txt[1:]
    if txt in NIM_KEYWORDS:
        txt = f"`{txt}`"
    return txt
#----------- EXPORTING  

def export_params(params):
    _params = ""
    n = 0
    for p in  params:
        if n > 0:
            _params += ", "
        if p[0]:
            _params += clean(p[0]) + ": "
        _type = get_nim_type(p[1])
        if len(p) > 2:
            if p[2] != None:
                _type += f" = {p[2]}"

        _params += _type
        n += 1
    return _params 


def get_comment(data, n = 4):
    spc = " " * n
    _tmp = ""
    _comment = data["comment"]
    if  _comment != None:
        _comment = textwrap.fill(_comment, width=70).split("\n")
        for i in _comment:
            _tmp += f"{spc}## {i}\n"
    return _tmp

def get_template_parameters(methodname):  # ÑAPA
    if '<' in methodname and '>' == methodname[-1]:
        _a, _b = methodname.split('<')
        _b = _b[:-1]
        return (_a, f"[{_b}]")
    else:
        return(methodname, '')

def get_constructor(data):
    _params = export_params(data["params"])   
    _tmp = ""
    if _params != "":
        _tmp = "(@)"

    # Templates
    methodname, templateparams = get_template_parameters(data["name"])
    _tmp = f'proc construct{methodname}*{templateparams}({_params}): {data["class_name"]} {{.constructor,importcpp: "{data["fully_qualified"]}{_tmp}".}}\n'
    _tmp += get_comment(data)  + "\n"
    return _tmp    

def get_method(data):
    # Parameters
    _params = export_params(data["params"])
    if _params != "":
        _params = ", " + _params

    # - Bear in mind the 'in-place' case
    _classname = data["class_name"]
    if not data["const_method"]:
        _classname = f"var {_classname}"

    _params = f'this: {_classname}{_params}'

    # Returned type
    _return = ""
    if data["result"] not in ["void", "void *"]:
        _result = data["result"].strip()
        if _result.startswith("const "):
            _result = _result[6:]
        if _result[-1] == "&":
            _result = _result[:-1].strip()
        _result = get_nim_type( _result )
        _return = f': {_result}'

    # Method name (lowercase the irst letter)
    _methodName = data["name"]
    _methodName = _methodName[0].lower() + _methodName[1:]
    _importName = data["name"]
    #_importName = data["fully_qualified"]    

    # Operator case
    if _importName.startswith("`") and _importName.endswith("`"):
        _importName = _importName[1:-1]
        _importName = f"# {_importName} #"
    
    # Templates
    _templParams = ""
    if "templParams" in data:
        if len(data["templParams"]) > 0:
            _templParams = "[" + ";".join( data["templParams"] ) + "]"
    _methodName = clean(_methodName)
    _tmp = f'proc {_methodName}*{_templParams}({_params}){_return}  {{.importcpp: "{_importName}".}}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp

def get_typedef(name, data, include = None):   # TODO: añadir opción si no está referenciado, comentar
    _type = get_nim_type( data["underlying"] )
    _include = ""
    if include != None:
        _include = f'header: "{include}", '

    if data["is_function_proto"]:
        # ActiveTextureProc* = proc (texture: GLenum)
        _return = ""
        if data["result"] not in ["void", "void *"]:
            _result = data["result"].strip()
            if _result.startswith("const "):
                _result = _result[6:]
            if _result[-1] == "&":
                _result = _result[:-1].strip()
            _result = get_nim_type( _result )
            _return = f': {_result}'        
        _params = export_params(data["params"])
        #if _params != "":
        #    _params = ", ".join(_params)
        
        _tmp = f"proc ({_params}){_return}"
        _name = clean(name)
        _name = _name[0].upper() + _name[1:]
        
        return f'  {_name}* {{.{_include}importcpp: "{data["fully_qualified"]}".}} = {_tmp}\n'
    else:
        _name = clean(name)  
        _name = _name[0].upper() + _name[1:]              
        return f'  {_name}* {{.{_include}importcpp: "{data["fully_qualified"]}".}} = {_type}\n'
    #_data[_file]["typedefs"].append((i["name"], _type))

def get_class(name, data, include = None, byref = True):
    #_name = data["name"]
    _include = ""
    if include != None:
        _include = f'header: "{include}", '
    _byref = ", byref" 
    if not byref:
        _byref = ", bycopy"
    _inheritance = ""
    if len(data["base"]) > 0:
        _inheritance = " #of "
        _inheritance += data["base"][0]   # Nim does not support multiple inheritance

    _nameClean = clean(name)
    _name = data["fully_qualified"]
    _tmp = f'  {_nameClean}* {{.{_include}importcpp: "{_name}"{_byref}.}} = object{_inheritance}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp    

def get_enum(name, data, include = None):
    _include = ""
    if include != None:
        _include = f'header: "{include}", '

    _type = get_nim_type(data["type"])
    _type = f"size:sizeof({_type})"

    _itemsTxt = ""
    _items = data["items"]
    n = len(_items)
    for i in range(len(_items)):
        _i = _items[i]
        _itemsTxt += f'    {_i["name"]} = {_i["value"]}'            
        if i<n-1:
            _itemsTxt += ","
        _itemsTxt += "\n"
        if _i["comment"] != None:
            _itemsTxt += get_comment(_i, n=6)

    #_items = ", ".join(_items)
    _name = name.split("::")[-1]
    _tmp = f'  {_name}* {{.{_type},{_include}importcpp: "{name}".}} = enum\n'
    if data["comment"] != None:
        _tmp += get_comment(data) + "\n"
    _tmp += _itemsTxt + "\n"
    return _tmp 

def get_const(data, include = None):
    _tmp = ""
    for i in data["items"]:
        _tmp += f'  {i["name"]}* = {i["value"]}\n'
        if i["comment"] != None:
            _tmp += get_comment(data) + "\n"
    return _tmp


def export_per_file( data, files = [], output= "occt", filter=None, \
                     dependencies = {}, root = "", filter_params = {}):
    _newfiles = []
    filtered_files = [i for i in files if i.startswith(filter)]
    for _file in filtered_files:
        _typedefs     = []
        _constructors = []
        _methods      = []
        _classes      = []
        _enums        = []
        _const        = []
        for item in data:
            if _file in item[0]:
                _tmpFile = _file.split(filter)[1]
                if item[1] == "constructor":
                    _constructors.append(get_constructor(item[2]))
                elif item[1] in ["method", "template"]:
                    _methods.append(get_method(item[2]))
                elif item[1] == "typedef":
                    _typedefs.append( get_typedef(item[2], _tmpFile))
                elif item[1] == "class":
                    if _file in filter_params:
                        if item[2] in filter_params[_file]:   
                            _classes.append(get_class(item[2], _tmpFile))
                elif item[1] == "enum":
                    _enums.append(get_enum(item[2], _tmpFile))  
                elif item[1] == "const":
                    if _file in filter_params:                    
                        if item[2] in filter_params[_file]:
                            _const.append(get_const(item[2], _tmpFile))                                   
        _fname = ""
        _popfile = None
        if filter != None:
            _fname = _file.split(filter)[1]
            _popfile = _fname
        _fname = os.path.splitext(_fname)[0]
        _nimname = _fname + ".nim"
        _newfiles.append( _nimname)        
        _fname = os.path.join(output, _nimname)
        #my_dict["const"] = my_dict["const"] + _const

        #if len(_typedefs) > 0 or len(_classes) > 0 or len(_enums) > 0:
        #    for _i in _enums:
        #        _fp1.write(_i)             
        #    for _i in _typedefs:
        #        _fp1.write(_i)
        #    for _i in _classes:
        #        _fp1.write(_i)                
        #my_dict["enums"] = my_dict["enums"] + _enums
        #my_dict["typedefs"] = my_dict["typedefs"] + _typedefs
        #my_dict["class"] = my_dict["class"] + _classes
        
        # Imports
        _fp = open(_fname, "w")
        if _file in dependencies:
            imports = {}
            for _dep in dependencies[_file]:
                #pprint(_dep)
                try:
                    _importName = _dep["include"].split(filter)[1]
                except:
                    _importName = _dep["include"].split("/")[-1]
                    _importName = _importName.split(".")[0]
                _value = imports.get(_importName, [])
                _value.append(_dep["name"])
                imports.update( {_importName:_value})
            #pprint(filter_params)
            for k, v in imports.items():
                _tmp = k.split('.')[0]
                _flag = True
                for _f, _v in filter_params.items():
                    if k in _v:
                        _flag = False
                #for _f, _v in filter_params["type"]:
                #    if k in _v:
                #        _flag = False                        
                #if k in 
                _fp.write(f'import {_tmp} # Provides {", ".join(v)}\n')
            _fp.write('\n\n')
        _fp.close()

        if len(_const) > 0:
            _fp = open(_fname, "a+")
            _fp.write("const\n")
            for _i in _const:
                _fp.write(_i)
            _fp.close()                 
        #pprint(_classes)         
        if len(_classes) > 0 or len(_enums) > 0 or len(_typedefs) > 0:
            _fp = open(_fname, "a+")
            _fp.write("type\n")
            if len(_enums) > 1:
                _fp.write("  # Enums\n")
            for _i in _enums:
                _fp.write(_i)
            if len(_typedefs) > 1:
                _fp.write("  # Typedefs\n")                   
            for _i in _typedefs:
                _fp.write(_i)                
            if len(_classes) > 1:
                _fp.write("  # Objects\n")                
            for _i in _classes:
                _fp.write(_i)
            _fp.close()                        
        if len(_constructors) > 0 or len(_methods) > 0:
            #print("METHODS")
            _fp = open(_fname, "a+")
            _fp.write(f'{{.push header: "{_popfile}".}}\n')        
            _fp.write("\n\n# Constructors and methods\n")
            for _i in _constructors:
                _fp.write(_i)
            for _i in _methods:
                _fp.write(_i)        
            _fp.write(f'{{.pop.}} # header: "{_popfile}\n')
            _fp.close()

    #_fp1.close()

def get_root(_blob):
    # Case where a specific file is given (no blob)
    if "*" not in _blob and "?" not in _blob:
        _tmp = _blob.split("/")
        _out = ""
        for i in _tmp[:-1]:
            _out += i + "/"
        return _out
    # Blob case
    _tmp = _blob.split("/")
    _out = ""
    for i in _tmp:
        if "*" not in i:
            _out += i + "/"
    return _out



def get_params_from_node(mynode):
    _params = []
    for i in mynode.get_children():
        if i.kind == clang.cindex.CursorKind.PARM_DECL:
            _paramName = i.displayname

            _default = None
            # Getting default values in params
            for j in i.get_children():
                for k in j.get_children():                                  
                    if k.kind == clang.cindex.CursorKind.UNEXPOSED_EXPR:
                        for m in k.get_tokens():
                            _default = m.spelling
                    if k.kind == clang.cindex.CursorKind.INTEGER_LITERAL:
                        try:
                            _default = k.get_tokens().__next__().spelling 
                        except:
                            pass  
            _params.append((i.displayname, i.type.spelling, _default))                                                          
    return _params    

def fully_qualified(c):
    if c is None:
        return ''
    elif c.kind == clang.cindex.CursorKind.TRANSLATION_UNIT:
        return ''
    else:
        res = fully_qualified(c.semantic_parent)
        if res != '':
            return res + '::' + c.spelling
    return c.spelling

NORMAL_TYPES = ["void", "long", "unsigned long", "int", "size_t", "long long", "long double", 
                "float", "double", "char", "signed char", "unsigned char", "unsigned short", 
                "unsigned int", "unsigned long long", "char*", "bool" ]

def cleanit(tmp):
    if tmp.startswith("const "):
        tmp = tmp[6:]
    if tmp[-1] in ["&", "*"]:
        tmp = tmp[:-2]    
    return tmp

def get_nodes(node,depth=0):
    """Traverse the AST tree
    """
    yield (depth, node)
    for child in node.get_children():
        yield from get_nodes(child, depth = depth+1)

"""
    if node.kind == clang.cindex.CursorKind.OVERLOADED_DECL_REF:
    elif node.kind == clang.cindex.CursorKind.TEMPLATE_REF:
    elif node.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
"""

class ParseFile:
    """
    This is used to parse C++ include files
    """
    def __init__(self, filename ):
        self.filename = filename
        self.index = clang.cindex.Index.create()
        _args = ['-x', 'c++',  f"-I{_folder}"]  # "-Wall", '-std=c++11', '-D__CODE_GENERATOR__'
        #opts = TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES # a bitwise or of TranslationUnit.PARSE_XXX flags.
        _opts = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        self.tu = self.index.parse(filename, _args, None, _opts)
        #--- Data
        self.consts = []
        self.enums = {}
        self._parse_enums()

        self.typedefs = {}
        self._parse_typedef()

        self.classes = {}
        self._parse_class()

        self.constructors = [] # Methods and operators
        self._parse_constructors()

        self.methods = [] # Methods and operators
        self._parse_methods()

        self.dependsOn = set([])
        self._find_depends_on()

        self.provides = set([])
        self._find_provided()

        self.missing = set([])
        self._missing_dependencies()


    def _parse_enums(self):
        """This function aims to extract all the anonymous enums"""
        for depth,node in get_nodes( self.tu.cursor, depth=0 ):
            _tmp = {}
            _isConst = False
            if node.kind == clang.cindex.CursorKind.ENUM_DECL and node.location.file.name == self.filename:
                _name = fully_qualified(node.referenced)
                if node.spelling == "":
                    _isConst = True
                else:
                    _isConst = False
                _tmp = {"comment": node.brief_comment,
                        "type": node.enum_type.spelling,
                        "items" : []}
                for _depth, n in get_nodes(node, depth):
                    if n.kind == clang.cindex.CursorKind.ENUM_CONSTANT_DECL:                        
                        _tmp["items"].append( { "name"   : n.spelling,
                                                "comment": n.brief_comment,
                                                "value"  : n.enum_value} )
                if _isConst:
                    #_tmp.pop("name")
                    self.consts.append(_tmp) # Just in case there are several const definitions
                else:
                    # Sort list
                    _values = [i["value"] for i in _tmp["items"]]
                    _values.sort()
                    _new = []
                    for i in _values:
                        for item in _tmp["items"]:
                            if item["value"] == i:
                                _new.append( item )
                    _tmp["items"] = _new
                    self.enums.update({_name : _tmp})

    def _parse_class(self):
        """Parse classes (not forward declarations)"""
        for depth,node in get_nodes( self.tu.cursor, depth=0 ):
            if node.kind in [clang.cindex.CursorKind.CLASS_DECL, clang.cindex.CursorKind.CLASS_TEMPLATE] and \
               node.is_definition() and node.location.file.name == self.filename:             
                _tmp = { "name" : node.spelling,
                         "comment": node.brief_comment,
                         "base" : [],
                         "fully_qualified": fully_qualified(node.referenced),
                         "template_params" : []
                       }                    
                #access_specifier: AccessSpecifier.PUBLIC
                #availability: AvailabilityKind.AVAILABLE
                for _, n in get_nodes( node, depth=depth ):
                    if n.kind == clang.cindex.CursorKind.CXX_BASE_SPECIFIER:
                        _tmp["base"].append(n.displayname)


                # Get template parameters
                for _, n in get_nodes(node, depth):
                    if n.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
                        _tmp["template_params"].append(n.spelling)

                _name = _tmp["name"]
                _tmp.pop("name")
                self.classes[_name] = _tmp

    def _parse_typedef(self):
        for depth,node in get_nodes( self.tu.cursor, depth=0 ):
            if node.kind in [clang.cindex.CursorKind.TYPEDEF_DECL] and \
               node.location.file.name == self.filename:  
                _name = node.displayname
                _tmp = { 
                         "underlying": node.underlying_typedef_type.spelling,
                         "is_function_proto": False,
                         "fully_qualified": fully_qualified(node.referenced),
                         "result": node.result_type.spelling              
                       }
                
                self.typedefs.update({_name : _tmp})
        
        #_data["params"] = get_params_from_node(node)
        """
        _kind = node.underlying_typedef_type.kind
        if _kind == clang.cindex.TypeKind.POINTER:
            _pointee = node.underlying_typedef_type.get_pointee()

            if _pointee.kind == clang.cindex.TypeKind.FUNCTIONPROTO:
                _result = _pointee.get_result().spelling
                _data["result"] = _result
                _data["is_function_proto"] = True
        """

    def _parse_constructors(self):
        for depth,node in get_nodes( self.tu.cursor, depth=0 ):
            if node.kind in [clang.cindex.CursorKind.CONSTRUCTOR] and \
               node.location.file.name == self.filename:   
                _tmp = { "name" : node.spelling,
                  "class_name": node.semantic_parent.spelling,
                  "comment": node.brief_comment,
                  "fully_qualified": fully_qualified(node.referenced) }
                _tmp["params"] = get_params_from_node(node)
                self.constructors.append(_tmp)

    def _parse_methods(self):
        """Parse methods and operators"""
        for depth,node in get_nodes( self.tu.cursor, depth=0 ):
            if node.kind in [clang.cindex.CursorKind.CXX_METHOD] and \
               node.location.file.name == self.filename:    
                _name = node.spelling
                if _name.startswith("operator"):
                    _tmp = _name[8:]
                    if re.match("[+-=*\^/]+", "+-+=*^"):
                        _name = f'`{_tmp}`'
                
                _tmp = {"name" : _name,
                        "fully_qualified" : fully_qualified(node.referenced),
                        "result" : node.result_type.spelling,
                        "class_name": node.semantic_parent.spelling,
                        "const_method": node.is_const_method(),
                        "comment" : node.brief_comment,
                        "file_origin" : node.location.file.name }
        
                _tmp["params"] = get_params_from_node(node)
                self.methods.append(_tmp)
    def _find_depends_on(self):
        """Find all dependences in the file"""
        _dependsOn = []
        for i in self.methods:
            for param in i["params"]:
                _dependsOn.append(cleanit(param[1]))
            if i["result"] != None:
                _dependsOn.append(cleanit(i["result"]))
        
        for _,v in self.typedefs.items():
            _dependsOn.append(cleanit(v["underlying"]))
        self.dependsOn = set(_dependsOn)

    def _find_provided(self):
        """Find all types that the file might provide to others"""
        # Dependencies
        _provides = []
        for i in self.consts:
            for item in i["items"]:
                if item["name"] in self.dependsOn:
                    _provides.append(item["name"])
        for k,_ in self.enums.items():
            _provides.append(k)
        for k,v in self.classes.items():
            _provides.append(v["fully_qualified"])
        for k,v in self.typedefs.items():
            _provides.append(v["fully_qualified"])

        self.provides = set(_provides)

    def _missing_dependencies(self):
        for i in self.dependsOn:
            if i not in NORMAL_TYPES and i not in self.provides:
                self.missing.add( i )

    def export_txt(self, filter = {}, dependencies = {}, root= "/"):
        # Filtering consts, enums, typedefs and type
        _filter = { "const"   : [],
                    "enum"    : [], 
                    "typedef" : [],
                    "class"   : [] }
        if self.filename in filter:
            _set = filter[self.filename]
            for i in self.consts:
                if i in _set:
                    _filter["const"].append(i)
            for i,_ in self.enums.items():
                if i in _set:
                    _filter["enum"].append(i)  
            for k,v in self.typedefs.items():
                if v["fully_qualified"] in _set:
                    _filter["typedef"].append(v["fully_qualified"])                                    
            for k,v in self.classes.items():
                if v["fully_qualified"] in _set:
                    _filter["class"].append(v["fully_qualified"])   
        
        _filename = self.filename.split(root)[-1]
        _txt = ""

        #if len(dependencies.keys()) > 0:
        for i in dependencies.keys():
            _tmp = i.split('::')[-1]
            _tmp = _tmp.split('.')[0]
            _types = ', '.join(dependencies[i])
            _txt += f'import {_tmp}  # provides: {_types}\n'

        _consts = self.consts
        # Remove shared consts
        if (len(self.consts) - len(_filter["const"]) )> 0:
            _txt += "const\n"
            for i in self.consts:
                if i not in _filter["const"]:
                    _txt += get_const(i)
            _txt += "\n\n"
        _n = len(_filter["enum"]) + len(_filter["typedef"]) + len(_filter["class"])
        if (len(self.typedefs) + len(self.classes) + len(self.enums) - _n) > 0:
            _txt += "type\n"
            if len(self.enums) > 0:
                for name,data in self.enums.items():
                    if name not in _filter["enum"]:
                        _txt += get_enum(name,data, _filename)

            if len(self.typedefs) > 0:
                for name, data in self.typedefs.items():
                    if data["fully_qualified"] not in _filter["typedef"]:                    
                        _txt += get_typedef(name,data, _filename)

            if len(self.classes) > 0:
                for name, data in self.classes.items():
                    if data["fully_qualified"]  not in _filter["class"]:                    
                        _txt += get_class(name,data, _filename)
            _txt += "\n\n"
        
        _flag = (len(self.constructors) + len(self.methods)) >0
        if _flag:
            _txt += f'{{.push header: "{_filename}".}}\n\n'
        for i in self.constructors:
            _txt += get_constructor(i)

        for i in self.methods:
            _txt += get_method(i)

        if _flag:
            _txt += f'{{.pop.}}  # header: "{_filename}"\n'
        
        return _txt

def relationships( files ):
    """For each file it gives the files providing some dependencies (a set of dependencies)"""
    _new = {}
    for file in files.keys():
        _pf = files[file]
        #for missing in _pf.missing:
        _data = {}
        for f in files.keys():
            if f != file:
                _pf2 = files[f]
                _found = _pf.missing.intersection(_pf2.provides)
                if len(_found) > 0:
                    _data[f] = _found
        _new[file] = _data
    return _new


#==============================================================
if __name__ == '__main__':
    # Read the command line: it takes a glob and a destination
    _folder = sys.argv[1]
    _dest = sys.argv[2]
    _path = os.getcwd()
    _destination_folder = os.path.join(_path, _dest)
    try:
        os.mkdir(_destination_folder)
    except:
        pass
    # Get the files list
    _root = get_root(_folder)    
    _allfiles = glob.glob(_folder, recursive = True)
    _files = [f for f in _allfiles if os.path.isfile(f)]
    _dirs  = [f for f in _allfiles if not os.path.isfile(f)]

    print("Root folder: ", _root)
    # Create folders if needed
    for i in _dirs:
        _rel = os.path.relpath(i, _root)
        _folder = os.path.join(_dest,_rel)
        Path(_folder).mkdir(parents=True, exist_ok=True)
   
    #-----------------------------------------------------------
    #parsed = {}
    files = {}

    _nTotal = len(_files)
    _n = 1
    for include_file in _files:
        print(f"Parsing ({_n}/{_nTotal}): {include_file}")
        _n += 1
        pf = ParseFile(include_file)
        files[include_file] = pf
        #print( pf.export_txt( root = _root ) )

    # Find relationships: for each file, it founds what files are providing which types
    providers = relationships( files )  # Contain: file -> (file -> sets)

    _filter = {}
    for _, _dict in providers.items():
        for k, sets in _dict.items():
            _set = _filter.get(k, set([]))
            _set = _set.union(sets)
            _filter[k] = _set

    # Write files to folder
    for filename, pf in files.items():
        _txt = pf.export_txt( root = _root, filter = _filter, dependencies = providers[filename] ) 
        _fname = filename.split( _root )[-1]
        _fname = os.path.splitext(_fname)[0]
        _nimname = _fname + ".nim"
        #_newfiles.append( _nimname)        
        _fname = os.path.join(_destination_folder , _nimname)        
        _fp = open(_fname, "w")
        _fp.write( _txt )
        _fp.close()

    # Export the root file
    _fname = os.path.join(_dest,_dest) + ".nim"
    _fp1 = open(_fname, "w")
    _fp1.write('{.passL: "-losg -losgSim -losgAnimation -losgTerrain -losgDB -losgText -losgFX -losgUI -losgGA -losgUtil -losgManipulator -losgViewer -losgParticle -losgVolume -losgPresentation -losgWidget -losgShadow", passC:"-I/usr/include/osg" .}\n\n')

    # Get the text for the shared const, enum, typedef, class.
    _shared = { "const" : [],
                "enum" : [],
                "typedef"  : [],
                "class" : [] }
    for filename, d in providers.items():
        for file, objects in d.items():
            df = files[file]
            _fname = file.split(_root)[-1]
            for i in df.consts:
                if i in objects:
                    _shared["const"].append( get_const(i, _fname) )

            for k,v in df.enums.items():
                if k in objects:
                    _shared["enum"].append( get_enum(k,v, _fname) )            
            
            for k,v in df.typedefs.items():
                if v["fully_qualified"] in objects:
                    _shared["typedef"].append( get_typedef(k,v, _fname) )              

            for k,v in df.classes.items():
                if v["fully_qualified"] in objects:
                    _shared["class"].append( get_class(k,v, _fname) ) 
    
    # Write the shared consts and types
    if len(_shared["const"]) > 0:
        _fp1.write("const\n")
        for i in _shared["const"]:
            fp1.write( i )
        _fp1.write("\n\n")

    if ( len(_shared["enum"]) + len(_shared["typedef"]) + len(_shared["class"]) ) > 0:
        _fp1.write("type\n")
        
        for i in _shared["enum"]:
            _fp1.write( i )
        for i in _shared["typedef"]:
            _fp1.write( i )
        for i in _shared["class"]:
            _fp1.write( i )            

        _fp1.write("\n\n")


    # write the include files
    for _file,_ in files.items():
        _fname = _file.split(_root)[1]
        _fname = os.path.splitext(_fname)[0]
        #_fp1.write(f'include "{_fname}.nim"\n')
        _fp1.write(f'import {_fname}')
    _fp1.close()            
