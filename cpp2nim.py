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
TODO: 
Debe solventar los conflictos en el naming de los tipos presentes en osg_types. 
Por ejemplo, Type en StateAttribute y Type en Array

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

def flatten(L):
    if len(L) == 1:
        if type(L[0]) == list:
            result = flatten(L[0])   
        else:
            result = L
    elif type(L[0]) == list:
        result = flatten(L[0]) + flatten(L[1:])   
    else:
        result = [L[0]] + flatten(L[1:])
    return result

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
        #_tmp = _tmp.capitalize()

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
        else:
            _params += f'a{n:02d}: '
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
    _isOperator = False
    if _importName.startswith("`") and _importName.endswith("`"):
        _importName = _importName[1:-1]
        _importName = f"# {_importName} #"
        _isOperator = True
    
    # Templates
    _templParams = ""
    if "templParams" in data:
        if len(data["templParams"]) > 0:
            _templParams = "[" + ";".join( data["templParams"] ) + "]"
    _methodName = clean(_methodName)
    if _isOperator and _methodName in ["`=`"]:
        _tmp = f'proc {_methodName}*{_templParams}({_params})  {{.importcpp: "{_importName}".}}\n'
    elif _isOperator and _methodName in ["`[]`"]:
        _importName = "#[#]"
        _tmp = f'proc {_methodName}*{_templParams}({_params})  {{.importcpp: "{_importName}".}}\n'  
    else:
        _tmp = f'proc {_methodName}*{_templParams}({_params}){_return}  {{.importcpp: "{_importName}".}}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp

def get_typedef(name, data, include = None):   # TODO: añadir opción si no está referenciado, comentar
    #_type = ""
    #if "underlying_deps" in data:
    #    print(data["underlying"])
    #else:
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
    _template = ""
    if len(data["template_params"]) > 0:
        _tmpList = []
        for i in data["template_params"]:
            if type(i) == tuple:
                _tmp = i[0] + ":" + get_nim_type(i[1])
                _tmpList.append(_tmp)
            else:
                _tmpList.append(i)
        _template = f'[{"; ".join(_tmpList)}]'

        #_template = f'[{", ".join(data["template_params"])}] '
    _tmp = f'  {_nameClean}*{_template} {{.{_include}importcpp: "{_name}"{_byref}.}} = object{_inheritance}\n'
    _tmp += get_comment(data) + "\n"
    return _tmp    

def get_struct(name, data, include = None):
    _include = ""
    if include != None:
        _include = f'header: "{include}", '
    _byref = ", byref" 

    _nameClean = clean(name)
    _name = data["fully_qualified"]
    _template = ""
    """
    if len(data["template_params"]) > 0:
        _tmpList = []
        for i in data["template_params"]:
            if type(i) == tuple:
                _tmp = i[0] + ":" + get_nim_type(i[1])
                _tmpList.append(_tmp)
            else:
                _tmpList.append(i)
        _template = f'[{"; ".join(_tmpList)}]'

        #_template = f'[{", ".join(data["template_params"])}] '
    """
    #_tmp = f'  {_nameClean}*{_template} {{.{_include}importcpp: "{_name}"{_byref}.}} = object{_inheritance}\n'
    _tmp = f'  {_nameClean}* {{.{_include}importcpp: "{_name}".}} = object\n'
    _tmp += get_comment(data) + "\n"
    return _tmp

def get_enum(name, data, include = None):
    #pprint(data)
    _name = name.split("::")[-1]
    _prefix = "" #remove_vowels( _name )

    _include = ""
    if include != None:
        _include = f'header: "{include}", '

    _type = get_nim_type(data["type"])
    _type = f"size:sizeof({_type})"

    _itemsTxt = ""
    _items = data["items"]
    #pprint(_items)
    n = len(_items)
    for i in range(len(_items)):
        _i = _items[i]
        #print(_i)
        _itemsTxt += f'    {_prefix}{_i["name"]} = {_i["value"]}'            
        if i<n-1:
            _itemsTxt += ","
        _itemsTxt += "\n"
        if _i["comment"] != None:
            _itemsTxt += get_comment(_i, n=6)

    #_items = ", ".join(_items)

    _tmp = f'  {_name}* {{.{_type},{_include}importcpp: "{name}", pure.}} = enum\n'
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

def get_template_dependencies(tmp):
    result = []
    _tmp = cleanit(tmp)
    if _tmp[-1] == ">" and "<" in _tmp: # In case is based on a template
        _tmp = [i.split('>') for i in _tmp.split('<')]
        _tmp = flatten(_tmp)
        _tmp = [i.split(',') for i in _tmp]
        _tmp = flatten(_tmp)
        _tmp = [i.strip() for i in _tmp if i.strip() != '']
        _tmp = [cleanit(i) for i in _tmp if not i.isdigit()]
        result = _tmp           
    return result


class ParseFile:
    """
    This is used to parse C++ include files
    """
    def __init__(self, filename ):
        self.filename = filename
        self.index = clang.cindex.Index.create()
        _args = ['-x', 'c++',  f"-I{_folder}"]  # "-Wall", '-std=c++11', '-D__CODE_GENERATOR__'
        #opts = TranslationUnit.PARSE_INCOMPLETE | TranslationUnit.PARSE_SKIP_FUNCTION_BODIES # a bitwise or of TranslationUnit.PARSE_XXX flags.
        _opts = clang.cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD | clang.cindex.TranslationUnit.PARSE_INCOMPLETE | clang.cindex.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
        #_opts = 
        self.tu = self.index.parse(filename, _args, None, _opts)
        #--- Data
        self.consts = []
        self.enums = {}
        self.repeated = {}
        self._parse_enums()

        self.typedefs = {}
        self._parse_typedef()
        #pprint(self.typedefs)

        self.classes = {}
        self._parse_class()

        self.structs = {}
        self._parse_struct()

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
                _typeName = fully_qualified(node.referenced)
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
                    _values = list(set(_values))
                    _values.sort()
                    _names = [i["name"] for i in _tmp["items"]]                    
                    _new = []
                    for i in _values:
                        for item in _tmp["items"]:
                            if item["value"] == i:
                                _new.append( item )
                                _names.remove(item["name"])
                                break
                    for _name in _names:
                        for item in _tmp["items"]:
                            if item["name"] == _name:
                                self.repeated[_name] = item
                    _tmp["items"] = _new
                    self.enums.update({_typeName : _tmp})

    def _parse_struct(self):
        for depth,node in get_nodes( self.tu.cursor, depth=0 ):
            if node.kind == clang.cindex.CursorKind.STRUCT_DECL and node.location.file.name == self.filename:
                _tmp = { "name" : node.spelling,
                         "comment": node.brief_comment,
                         "base" : [],
                         "fully_qualified": fully_qualified(node.referenced),
                         "template_params" : []
                       }
                self.structs.update( {node.spelling : _tmp} )              

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
                if node.kind == clang.cindex.CursorKind.CLASS_TEMPLATE:
                    #print(depth)         
                    for _depth, n in get_nodes(node, depth):
                        #print(_depth, n.spelling, n.kind)
                        if n.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
                            _flag = False
                            _tmp["template_params"].append(n.spelling)
                        elif n.kind == clang.cindex.CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
                            _templateParam = (n.spelling,n.type.spelling)
                            _flag = False
                            _tmp["template_params"].append(_templateParam)                            
                        elif n.kind in [clang.cindex.CursorKind.CLASS_TEMPLATE, clang.cindex.CursorKind.TYPE_REF]:
                            pass 
                        else:
                            break

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


                # Underlying dependencies
                _tmp["underlying_deps"] = get_template_dependencies(_tmp["underlying"])


                # The typedef might be for a function
                _tmp["params"] = get_params_from_node(node)
                
                _kind = node.underlying_typedef_type.kind
                if _kind == clang.cindex.TypeKind.POINTER:
                    _pointee = node.underlying_typedef_type.get_pointee()

                    if _pointee.kind == clang.cindex.TypeKind.FUNCTIONPROTO:
                        _result = _pointee.get_result().spelling
                        _tmp["result"] = _result
                        _tmp["is_function_proto"] = True                
                self.typedefs.update({_name : _tmp})

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
                    
                #print(_tmp["result"])                    
                #pprint(_tmp["result_deps"])
                #if "<" in _tmp["result"]:
                _tmp["result_deps"] = get_template_dependencies(_tmp["result"])
                #    pprint(_tmp)
                # Methods dependencies for results

                _tmp["params"] = get_params_from_node(node)
                self.methods.append(_tmp)

    def _find_depends_on(self):
        """Find all dependences in the file"""
        _dependsOn = []

        for i in (self.methods+self.constructors):
            for param in i["params"]:
                # Param type
                _tmp1 = get_template_dependencies(param[1])
                if _tmp1 != []:
                    for j in _tmp1:
                        _dependsOn.append(j)
                else:
                    _dependsOn.append(cleanit(param[1]))

                # Default value
                #if "Material" in self.filename:
                #    print(param)
                if param[2] != None:
                    #for k,val in self.enums.items():
                    #    for j in val["items"]:
                    #        print(j["name"])
                    #        if j["name"] == param[2]:
                    _dependsOn.append(param[2])
            if "result" in i:
                if i["result"] != None:
                    if i["result_deps"] != []:
                        for j in i["result_deps"]:
                            _dependsOn.append( j )
                    else:
                        _dependsOn.append(cleanit(i["result"]))

        for _,v in self.typedefs.items():
            if v["underlying_deps"] != []:
                for _i in v["underlying_deps"]:
                    _dependsOn.append( _i )
            else:            
                _tmp = cleanit(v["underlying"])
                _dependsOn.append( _tmp )

        self.dependsOn = set(_dependsOn)
        #pprint(self.dependsOn)

    def _find_provided(self):
        """Find all types that the file might provide to others"""
        # Dependencies
        _provides = []
        for i in self.consts:
            for item in i["items"]:
                if item["name"] in self.dependsOn:
                    _provides.append(item["name"])
        for k, v in self.enums.items():
            for i in v["items"]:
                _provides.append((i["name"],k))
            _provides.append(k)
        for k,v in self.classes.items():
            _provides.append(v["fully_qualified"])
        for k,v in self.structs.items():
            _provides.append(v["fully_qualified"])            
        for k,v in self.typedefs.items():
            _provides.append(v["fully_qualified"])

        self.provides = set(_provides)

    def _missing_dependencies(self):
        for i in self.dependsOn:
            if i not in NORMAL_TYPES:
                if i not in self.provides:
                    _tmp = [k[0] for k in self.provides if type(k) is tuple]
                    if i not in _tmp:
                        self.missing.add( i )

    def export_txt(self, filter = {}, dependencies = {}, root= "/", shared = None ):
        # Filtering consts, enums, typedefs and type
        _filter = { "const"   : [],
                    "enum"    : [], 
                    "typedef" : [],
                    "class"   : [],
                    "struct"  : []}

        if self.filename in filter:
            _set = filter[self.filename]
            
            for i in self.consts:
                for item in i["items"]:
                    if item["name"] in _set:
                        _filter["const"].append(item["name"])                  
            for i,_ in self.enums.items():
                if i in _set:
                    _filter["enum"].append(i)
 
            for k,v in self.typedefs.items():
                if v["fully_qualified"] in _set:
                    _filter["typedef"].append(v["fully_qualified"])
                    # We also consider their dependencies (they will be handled in the root file)
                    if "underlying_deps" in v:
                        for _i in v["underlying_deps"]:
                            if _i in self.classes:
                                _v = self.classes[_i]
                                _filter["class"].append( _v["fully_qualified"] )
            for k,v in self.classes.items():
                if v["fully_qualified"] in _set:
                    _filter["class"].append(v["fully_qualified"])

            for k,v in self.structs.items():
                if v["fully_qualified"] in _set:
                    _filter["struct"].append(v["fully_qualified"])
            
        _filename = self.filename.split(root)[-1]
        _txt = ""

        if len(dependencies.keys()) > 0:
            _txt += f'import {shared}\n'            
            for i in dependencies.keys():
                _tmp = i.split(root)[-1]
                _tmp = _tmp.split('.')[0]
                _types = ', '.join(dependencies[i])
                #_txt += f'import {_tmp}  # provides: {_types}\n'
                _txt += f'  # File: {_tmp}  was providing: {_types}\n'

        _consts = self.consts
        # Remove shared consts
        if (len(self.consts) - len(_filter["const"]) )> 0:
            _txt += "const\n"
            for i in self.consts:
                if i not in _filter["const"]:
                    _txt += get_const(i)
            _txt += "\n\n"
        _n = len(_filter["enum"]) + len(_filter["typedef"]) + len(_filter["class"]) + len(_filter["struct"])

        if (len(self.typedefs) + len(self.classes) + len(self.enums) + len(self.structs) - _n) > 0:
            _txt += "type\n"
            if len(self.enums) > 0:
                for name,data in self.enums.items():
                    if name not in _filter["enum"]:
                        _txt += get_enum(name,data, _filename)

            # Classes go before typedefs (typedefs might depend on them)
            if len(self.classes) > 0:
                for name, data in self.classes.items():
                    if data["fully_qualified"]  not in _filter["class"]:                    
                        _txt += get_class(name,data, _filename)

            if len(self.structs) > 0:
                for name, data in self.structs.items():
                    if data["fully_qualified"]  not in _filter["struct"]:                    
                        _txt += get_struct(name,data, _filename)

            if len(self.typedefs) > 0:
                for name, data in self.typedefs.items():
                    if data["fully_qualified"] not in _filter["typedef"]:                    
                        _txt += get_typedef(name,data, _filename)

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
                # The normal case
                _pf2 = files[f]
                _found = _pf.missing.intersection(_pf2.provides)
                if len(_found) > 0:
                    _data[f] = _found

                # The enum case
                _tmp = [k[0] for k in _pf2.provides if type(k) is tuple]
                _found2 = _pf.missing.intersection(_tmp)
                
                _enumFound = []
                if len(_found2) > 0:
                    for item in _found2:
                        for k in _pf2.provides:
                            if type(k) is tuple:
                                if item == k[0]:
                                    _enumFound.append( k[1])
                _enumFound = list(set(_enumFound))
                #print(_enumFound)
                if len(_found) > 0 or len(_enumFound) > 0:
                    _data[f] = set(list(_found) + _enumFound)


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
   
    # Start parsing all the include files
    files = {}

    _nTotal = len(_files)
    _n = 1
    for include_file in _files:
        print(f"Parsing ({_n}/{_nTotal}): {include_file}")
        _n += 1
        pf = ParseFile(include_file)
        files[include_file] = pf

    # Find relationships: for each file, it founds what files are providing which types
    providers = relationships( files )  # Contain: file -> (file -> sets)


    # The following contains: file-> objects provided
    _filter = {}
    for _, _dict in providers.items():
        for k, sets in _dict.items():
            _set = _filter.get(k, set([]))
            _set = _set.union(sets)

            _pf = files[k]
            _td = _pf.typedefs # Typedefs for the file
            for key, value in _td.items(): # Iterate on them
                if "underlying_deps" in value:  # For those having this field
                    for _i in value["underlying_deps"]:  # Iterate on their items
                        #print(_i)
                        if _i in _pf.classes:     # 
                            #_v = df.classes[_i]
                            _set.add( _pf.classes[_i]["fully_qualified"]) #shared["class"].append( get_class(_i,_v, _fname) )
                            #print("added")
            _filter[k] = _set

    # Write files to folder
    for filename, pf in files.items():
        _txt = pf.export_txt( root = _root, filter = _filter, dependencies = providers[filename], shared = _dest + "_types" ) 
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
                "class" : [],
                "struct": [] }
    #for filename, d in providers.items():
    #    for file, objects in d.items():
    for file, objects in _filter.items():
            df = files[file]
            _fname = file.split(_root)[-1]
            for i in df.consts:
                for item in i["items"]:
                    if item["name"] in objects:
                        _shared["const"].append( get_const(item, _fname) )

            for k,v in df.enums.items():
                if k in objects:
                    _shared["enum"].append( get_enum(k,v, _fname) )            
            
            for k,v in df.typedefs.items():
                if v["fully_qualified"] in objects:
                    _shared["typedef"].append( get_typedef(k,v, _fname) )
                    # We add the associated classes if any:
                    """
                    if "underlying_deps" in v:
                        for _i in v["underlying_deps"]:
                            if _i in df.classes:
                                _v = df.classes[_i]
                                _shared["class"].append( get_class(_i,_v, _fname) )
                    """
            for k,v in df.classes.items():
                if v["fully_qualified"] in objects:
                    _shared["class"].append( get_class(k,v, _fname) ) 
    
            for k,v in df.structs.items():
                if v["fully_qualified"] in objects:
                    _shared["struct"].append( get_struct(k,v, _fname) ) 

    # Check repeated identifiers in "_shared"
    _identifiers = [i for k,v in _shared.items() for i in v]
    _repeated = set([x for x in _identifiers if _identifiers.count(x) > 1])
    print(_repeated)


    # Write the shared consts and types
    _fname2 = os.path.join(_dest,_dest+ "_types") + ".nim"
    _fp2 = open(_fname2, "w")    
    if len(_shared["const"]) > 0:
        _fp2.write("const\n")
        for i in _shared["const"]:
            fp2.write( i )
        _fp2.write("\n\n")

    if ( len(_shared["enum"]) + len(_shared["typedef"]) + len(_shared["class"]) + len(_shared["struct"]) ) > 0:
        _fp2.write("type\n")
        
        for i in _shared["enum"]:
            _fp2.write( i )
        for i in _shared["class"]:
            _fp2.write( i )       
        for i in _shared["struct"]:
            _fp2.write( i )                     
        for i in _shared["typedef"]:
            _fp2.write( i )
           

        _fp2.write("\n\n")
    _fp2.close()
    # write the include files
    for _file,_ in files.items():
        _fname = _file.split(_root)[1]
        _fname = os.path.splitext(_fname)[0]
        #_fp1.write(f'include "{_fname}.nim"\n')
        _fp1.write(f'import {_fname}\n')
    _fp1.close()            
